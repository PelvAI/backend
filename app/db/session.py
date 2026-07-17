from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL")
# NOTA PARA DESARROLLO/SERVIDOR:
# - En producción/staging, asegúrese de definir la variable de entorno DATABASE_URL en el servidor.
# - En local, si tiene un PostgreSQL nativo en macOS (puerto 5432) en conflicto con Docker:
#   1. Apague el Postgres nativo (`brew services stop postgresql`) para que Docker reciba la conexión en el 5432.
#   2. O cree un archivo `.env` local (ignorado por Git) definiendo DATABASE_URL apuntando a un puerto alternativo (ej. 5433).
if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://alma:alma_secret@127.0.0.1:5432/alma_db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
