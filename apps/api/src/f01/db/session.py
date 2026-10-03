from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


class Database:
    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
            echo=False,
        )

    def session(self, *, snapshot: bool = False) -> Session:
        bind = (
            self.engine.execution_options(isolation_level="REPEATABLE READ")
            if snapshot
            else self.engine
        )
        return Session(bind, expire_on_commit=False)

    def close(self) -> None:
        self.engine.dispose()
