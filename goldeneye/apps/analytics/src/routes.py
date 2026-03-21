from fastapi import APIRouter

router = APIRouter(prefix="/analytics")


@router.get("/summary")
def get_summary():
    return {
        "message": "Analytics summary endpoint",
        "data": [],
    }
