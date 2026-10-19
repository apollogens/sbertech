"""FastAPI: загрузка истории, прогнозирование и чтение последнего прогноза."""

import os
import sys
import hashlib
import multiprocessing
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .predictor import Predictor
from .validators import InputError, read_csv, validate_history


def csv_chunks(frame, chunk_size=10000):
    if frame.empty:
        yield frame.to_csv(index=False)
    for start in range(0, len(frame), chunk_size):
        yield frame.iloc[start:start + chunk_size].to_csv(index=False, header=start == 0, float_format="%.17g")


def json_chunks(frame, chunk_size=10000):
    yield "["
    for start in range(0, len(frame), chunk_size):
        if start:
            yield ","
        yield frame.iloc[start:start + chunk_size].to_json(orient="records", double_precision=15)[1:-1]
    yield "]"


def snapshot_headers(frame):
    metadata = frame.attrs.get("cache_metadata", {})
    headers = {"X-Forecast-Version": str(metadata.get("version", "")),
               "X-Model-ID": metadata.get("model_id", "")}
    for name, digest in metadata.get("input_sha256", {}).items():
        headers[f"X-Input-{name}-SHA256"] = digest
    return headers


def csv_response(frame, filename):
    return StreamingResponse(csv_chunks(frame), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', **snapshot_headers(frame)})


def enforce_single_worker():
    """Память кэша локальна процессу; многопроцессный запуск запрещён."""
    counts = [os.environ.get(name, "1") for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS")]
    arguments = sys.argv[1:]
    for position, argument in enumerate(arguments):
        if argument in ("--workers", "-w"):
            counts.append(arguments[position + 1] if position + 1 < len(arguments) else "invalid")
        elif argument.startswith("--workers="):
            counts.append(argument.split("=", 1)[1])
        elif argument.startswith("-w") and argument[2:].isdigit():
            counts.append(argument[2:])
    if any(value != "1" for value in counts) or multiprocessing.current_process().name != "MainProcess":
        raise RuntimeError("Forecast cache requires exactly one worker; start uvicorn with --workers 1")


def create_app(predictor=None):
    @asynccontextmanager
    async def lifespan(application):
        enforce_single_worker()
        if predictor is not None:
            application.state.predictor = predictor
        elif os.environ.get("FORECAST_CONFIG"):
            from src.runtime import configured_bundle
            bundle = await run_in_threadpool(configured_bundle, os.environ["FORECAST_CONFIG"])
            application.state.predictor = Predictor(bundle)
        elif os.environ.get("MODEL_DIR"):
            application.state.predictor = await run_in_threadpool(Predictor.load, Path(os.environ["MODEL_DIR"]))
        else:
            from src.runtime import configured_selection, load_bundle
            model_dir, strategy = configured_selection()
            if strategy == "nonton-v1":
                application.state.predictor = await run_in_threadpool(Predictor.load, model_dir)
            else:
                bundle = await run_in_threadpool(load_bundle, model_dir, strategy)
                application.state.predictor = Predictor(bundle)
        yield

    application = FastAPI(title="Nonton Forecast API", version="1.0.0", lifespan=lifespan)

    @application.exception_handler(InputError)
    async def input_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "code": "VALIDATION_ERROR"})

    @application.exception_handler(RequestValidationError)
    async def request_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": "Missing or invalid request parameters", "code": "VALIDATION_ERROR"})

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail), "code": "VALIDATION_ERROR" if exc.status_code in (400, 422) else "REQUEST_ERROR"})

    def cached(request):
        frame = request.app.state.predictor.get_cached_forecast()
        if frame is None:
            raise HTTPException(409, "No forecast yet; call POST /predict first")
        return frame

    @application.get("/health")
    def health(request: Request):
        config = request.app.state.predictor.bundle.get("config", {})
        return {"status": "ok", "model_loaded": True, "model_version": config.get("model_version", config.get("version", "1"))}

    @application.get("/diagnostics")
    def diagnostics(request: Request):
        return request.app.state.predictor.diagnostics()

    @application.post("/predict")
    def predict_post(request: Request, sales: UploadFile = File(...), stock: UploadFile = File(...)):
        engine = request.app.state.predictor
        if not engine.post_lock.acquire(blocking=False):
            raise HTTPException(409, "Another prediction request is running")
        try:
            payloads = {"sales": sales.file.read(), "stock": stock.file.read()}
            identity = {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}
            sales_frame = validate_history(read_csv(payloads["sales"], "sales"), "sales", engine.catalogs)
            stock_frame = validate_history(read_csv(payloads["stock"], "stock"), "stock", engine.catalogs)
            del payloads
            try:
                result = engine.predict(sales_frame, stock_frame, input_identity=identity)
            except Exception as exc:
                # Не раскрываем внутренние пути/модельные данные клиенту.
                import logging
                logging.getLogger(__name__).exception("Forecast inference failed")
                raise HTTPException(500, "Forecast inference failed") from exc
            return csv_response(result, "forecast.csv")
        finally:
            engine.post_lock.release()

    @application.get("/predict")
    def predict_get(request: Request, article: str | None = Query(None), warehouse: str | None = Query(None)):
        if not article and not warehouse:
            raise HTTPException(400, "Specify article or warehouse")
        frame = cached(request)
        if article:
            frame = frame[frame.article == article]
        if warehouse:
            frame = frame[frame.warehouse_name == warehouse]
        if frame.empty:
            raise HTTPException(404, "Unknown article or warehouse")
        return csv_response(frame, "filtered_forecast.csv")

    @application.get("/predict/all")
    def predict_all(request: Request, format: str = Query("csv")):
        if format not in ("csv", "json"):
            raise HTTPException(400, "format must be csv or json")
        frame = cached(request)
        if format == "json":
            return StreamingResponse(json_chunks(frame), media_type="application/json", headers=snapshot_headers(frame))
        return csv_response(frame, "full_forecast.csv")

    return application


app = create_app()
