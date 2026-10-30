class FakeS3Client:
    """Just enough of the boto3 S3 client for Storage."""

    class exceptions:
        class ClientError(Exception):
            def __init__(self, code="404"):
                self.response = {"Error": {"Code": code}}

    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.presigned_posts: list[dict] = []

    def generate_presigned_post(self, Bucket, Key, Fields, Conditions, ExpiresIn):
        self.presigned_posts.append({"Key": Key, "Conditions": Conditions, "ExpiresIn": ExpiresIn})
        return {"url": f"https://{Bucket}.s3.test/", "fields": {"key": Key, **Fields}}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.ClientError("404")
        o = self.objects[Key]
        return {"ContentLength": o["size"], "ContentType": o["content_type"]}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://{Params['Bucket']}.s3.test/{Params['Key']}?expires={ExpiresIn}"

    def put(self, key: str, size: int, content_type: str):
        self.objects[key] = {"size": size, "content_type": content_type}
