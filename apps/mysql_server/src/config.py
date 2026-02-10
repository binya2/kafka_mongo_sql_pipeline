from pydantic import Field
from pydantic_settings import BaseSettings


class MySqlConfig(BaseSettings):
    host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    user: str = Field(default="root", validation_alias="MYSQL_USER")
    password: str = Field(default="root_password", validation_alias="MYSQL_PASSWORD")
    database: str = Field(default="week_17_pro_db", validation_alias="MYSQL_DATABASE")
    pool_size: int = Field(default=5, validation_alias="POOL_SIZE")
    pool_name: str = Field(default="week_17_pro_pool", validation_alias="POOL_NAME")
    autocommit: bool = Field(default=True, validation_alias="AUTO_COMMIT")


mysql_config = MySqlConfig()
