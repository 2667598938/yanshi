"""图片对象存储：本地文件（开发）与七牛 Kodo S3（生产）。

对象 key 形如 avatar/3/ab12....jpg，目录即业务类型 + 用户；访问一律走带鉴权的
view 接口，七牛私有 bucket 由服务端生成短期 S3 签名 URL 后 302 跳转。
"""
import re
import shutil

from ..errors import ApiError

KEY_RE = re.compile(r'(avatar|mistake|school|inspiration|ai)/[0-9]+/[a-f0-9]{32}\.jpg')


class ImageStorage:
    def __init__(self, settings):
        self.s = settings

    def path(self, key):
        if not KEY_RE.fullmatch(key):
            raise ApiError(400, 40001, '图片标识无效')
        root = self.s.image_directory.resolve()
        target = (root / key).resolve()
        if not target.is_relative_to(root):
            raise ApiError(400, 40001, '图片路径无效')
        return target

    def _s3_client(self):
        import boto3
        from botocore.config import Config
        region = self.s.qiniu_s3_region
        return boto3.session.Session().client(
            's3', region_name=region,
            endpoint_url=f'https://s3.{region}.qiniucs.com',
            aws_access_key_id=self.s.qiniu_access_key,
            aws_secret_access_key=self.s.qiniu_secret_key,
            config=Config(signature_version='s3v4',
                          s3={'addressing_style': 'path'},
                          retries={'max_attempts': 2}))

    def save(self, key, src, size):
        if self.s.image_storage != 'qiniu':
            if self.s.environment == 'production':
                raise ApiError(503, 50301, '生产环境图片尚未配置七牛存储')
            path = self.path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            src.seek(0)
            try:
                with path.open('xb') as dest:
                    shutil.copyfileobj(src, dest, 64 * 1024)
                return
            except FileExistsError:
                raise ApiError(409, 40901, '图片标识冲突，请重试') from None
        if not self.s.qiniu_access_key:
            raise ApiError(503, 50301, '七牛存储未配置')
        client = self._s3_client()
        try:
            src.seek(0)
            client.put_object(Bucket=self.s.qiniu_bucket, Key=key,
                              Body=src.read(), ContentType='image/jpeg')
        except Exception:
            raise ApiError(502, 50201, '七牛图片上传失败，请稍后重试') from None
        finally:
            client.close()

    def delete(self, key):
        self.path(key)  # 先校验对象标识，避免删除任意路径
        if self.s.image_storage != 'qiniu':
            self.path(key).unlink(missing_ok=True)
            return
        client = self._s3_client()
        try:
            client.delete_object(Bucket=self.s.qiniu_bucket, Key=key)
        except Exception:
            raise ApiError(502, 50201, '图片删除失败，请稍后重试') from None
        finally:
            client.close()

    def presigned_url(self, key):
        client = self._s3_client()
        try:
            return client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s.qiniu_bucket, 'Key': key},
                ExpiresIn=300)
        except Exception:
            raise ApiError(502, 50201, '图片存储暂时不可用') from None
        finally:
            client.close()

    def read_private(self, key):
        self.path(key)  # 校验对象标识，不接受任意对象路径。
        client = self._s3_client()
        body = None
        try:
            body = client.get_object(Bucket=self.s.qiniu_bucket, Key=key)['Body']
            data = body.read(self.s.image_max_bytes + 1)
            if len(data) > self.s.image_max_bytes: raise ValueError('oversized')
            return data
        except Exception:
            raise ApiError(502,50201,'图片读取失败') from None
        finally:
            if body: body.close()
            client.close()
