from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', hide_input_in_errors=True)

    environment: str = 'development'  # development | test | production
    database_url: str = 'sqlite:///' + (BASE_DIR / 'data' / 'dev.sqlite').as_posix()

    # JWT
    jwt_secret: str = ''
    jwt_issuer: str = 'yanshi'
    jwt_audience: str = 'yanshi-web'
    access_seconds: int = Field(default=7200, ge=60, le=86400)        # 2 小时
    refresh_seconds: int = Field(default=1209600, ge=3600, le=2592000)  # 14 天

    # 跨域
    public_origin: str = 'http://localhost:27341'
    cors_origins: str = 'http://localhost:27341,http://127.0.0.1:27341,http://localhost:5173,http://127.0.0.1:5173'

    # 邮件（QQ SMTP 465 SSL；留空且 mail_console=true 时验证码打印到控制台）
    mail_console: bool = True
    smtp_host: str = ''
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    mail_directory: Path = BASE_DIR / 'data' / 'mail'

    # seed 初始管理员
    admin_email: str = '2667598938@qq.com'
    admin_password: str = ''

    # 图片存储：本地开发用 data/uploads；生产切七牛 Kodo（私有 bucket + S3 签名 URL）
    image_storage: str = 'local'   # local | qiniu
    image_directory: Path = BASE_DIR / 'data' / 'uploads'
    image_max_avatar_bytes: int = 2 * 1024 * 1024
    image_max_bytes: int = 5 * 1024 * 1024
    storage_quota_bytes: int = 200 * 1024 * 1024   # 每用户 200MB（4 人私密足够）
    qiniu_access_key: str = ''
    qiniu_secret_key: str = ''
    qiniu_bucket: str = 'sharearea'
    qiniu_s3_region: str = 'cn-south-1'
    qiniu_domain: str = ''                         # img.duzhi.xin（备案 + CNAME 后填）

    # AI：火山方舟豆包（Key 仅在服务端 .env，前端不接触、不做 BYOK）
    volc_api_key: str = ''
    volc_model: str = 'doubao-seed-2-1-pro-260915'
    volc_base_url: str = 'https://ark.cn-beijing.volces.com/api/v3'
    ai_max_tokens: int = 1200

    @property
    def ai_enabled(self):
        return bool(self.volc_api_key)

    @property
    def cors_list(self):
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]

    @property
    def is_sqlite(self):
        return self.database_url.startswith('sqlite')
