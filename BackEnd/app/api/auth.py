from fastapi import APIRouter, HTTPException, Request, Response

from BackEnd.app.service.session_service import SESSION_COOKIE, set_session

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

def register(request: Register, response: Response = None, http_request: Request = None):
    try:
        result=auth_service.register(request)
        if response is not None:
            set_session(response, result["user_id"], secure=http_request is not None and http_request.url.scheme == "https")
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
def login(request: Login, response: Response = None, http_request: Request = None):
    try:
        result = auth_service.login(request)

        if response is not None:
            set_session(response, result["user_id"], secure=http_request is not None and http_request.url.scheme == "https")
        return {
            "message": "Login successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )

@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the current browser session."""
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return {"message": "Logged out."}
