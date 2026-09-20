from fastapi import APIRouter, HTTPException

from BackEnd.app.database.sql_models import(
    Register, Login,
)

from BackEnd.app.service.auth_service import AuthService

router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)
auth_service=AuthService()

@router.post("/register")

def register(request: Register):
    try:
        result=auth_service.register(request)
        return {
            "message": "Register successfully",
            "data":result,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.post("/login")
def login(request: Login):
    try:
        result = auth_service.login(request)

        return {
            "message": "Login successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )