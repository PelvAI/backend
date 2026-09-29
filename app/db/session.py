from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# La cadena de conexión sale de un solo lugar. Antes este módulo la resolvía por
# su cuenta con os.getenv, que NO lee el archivo .env, mientras config.py sí lo
# leía: los dos daban valores distintos y el que abría la conexión era el que
# ignoraba el archivo.
#
# El efecto era desconcertante. docker-compose expone Postgres en el 5433 para
# no chocar con el Postgres nativo de la máquina; sin variable de entorno, esto
# intentaba el 5432, encontraba el nativo, fallaba con 'role "alma" does not
# exist' y entonces nada andaba, ni el login. Y el remedio que documentaba el
# propio comentario —crear un .env— no tenía ningún efecto acá.
#
# Para elegir la base: variable de entorno DATABASE_URL, o DATABASE_URL en el
# archivo .env. Las dos funcionan ahora, y la variable gana.
DATABASE_URL = get_settings().database_url

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
