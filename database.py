from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import config

Base = declarative_base()


class Info(Base):
    __tablename__ = "info"

    id = Column(Integer, primary_key=True)
    content = Column(Text, default="")


class Memory(Base):
    __tablename__ = "memory"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    content = Column(Text, default="")


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, default="")


class DisabledChat(Base):
    __tablename__ = "disabled_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)


engine = None
Session = None


def init_db():
    global engine, Session
    db_url = config.DATABASE_URL or "sqlite:///data.db"
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)


def get_session():
    return Session()


def read_info() -> str:
    session = get_session()
    try:
        info = session.query(Info).first()
        return info.content if info else ""
    finally:
        session.close()


def write_info(content: str):
    session = get_session()
    try:
        info = session.query(Info).first()
        if info:
            info.content = content
        else:
            info = Info(content=content)
            session.add(info)
        session.commit()
    finally:
        session.close()


def read_memory(user_id: int = None) -> str:
    session = get_session()
    try:
        if user_id:
            mem = session.query(Memory).filter_by(user_id=user_id).first()
            return mem.content if mem else ""
        else:
            mem = session.query(Memory).first()
            return mem.content if mem else ""
    finally:
        session.close()


def write_memory(user_id: int, content: str):
    session = get_session()
    try:
        mem = session.query(Memory).filter_by(user_id=user_id).first()
        if mem:
            mem.content = content
        else:
            mem = Memory(user_id=user_id, content=content)
            session.add(mem)
        session.commit()
    finally:
        session.close()


def read_setting(key: str) -> str:
    session = get_session()
    try:
        setting = session.query(Settings).filter_by(key=key).first()
        return setting.value if setting else ""
    finally:
        session.close()


def write_setting(key: str, value: str):
    session = get_session()
    try:
        setting = session.query(Settings).filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            session.add(setting)
        session.commit()
    finally:
        session.close()


def is_chat_disabled(chat_id: int) -> bool:
    session = get_session()
    try:
        disabled = session.query(DisabledChat).filter_by(chat_id=chat_id).first()
        return disabled is not None
    finally:
        session.close()


def set_chat_disabled(chat_id: int):
    session = get_session()
    try:
        existing = session.query(DisabledChat).filter_by(chat_id=chat_id).first()
        if not existing:
            session.add(DisabledChat(chat_id=chat_id))
            session.commit()
    finally:
        session.close()


def set_chat_enabled(chat_id: int):
    session = get_session()
    try:
        disabled = session.query(DisabledChat).filter_by(chat_id=chat_id).first()
        if disabled:
            session.delete(disabled)
            session.commit()
    finally:
        session.close()


def add_admin_id(admin_id: int):
    session = get_session()
    try:
        existing = session.query(Settings).filter_by(key="admin_ids").first()
        if existing:
            ids = set(int(x) for x in existing.value.split(",") if x.strip())
            ids.add(admin_id)
            existing.value = ",".join(str(x) for x in ids)
        else:
            setting = Settings(key="admin_ids", value=str(admin_id))
            session.add(setting)
        session.commit()
    finally:
        session.close()


def get_admin_ids() -> set[int]:
    session = get_session()
    try:
        setting = session.query(Settings).filter_by(key="admin_ids").first()
        if setting and setting.value:
            return set(int(x) for x in setting.value.split(",") if x.strip())
        return set()
    finally:
        session.close()