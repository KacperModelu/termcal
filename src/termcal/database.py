from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///./kario.db"
engine = create_engine(DATABASE_URL)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session()-> Session:
    return Session(engine)