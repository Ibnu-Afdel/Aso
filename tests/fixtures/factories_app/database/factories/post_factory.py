from fastogram.database import Factory

from app.models.post import Post


class PostFactory(Factory):
    model = Post

    def definition(self) -> dict:
        return {
            "title": self.faker.sentence(),
            "body": self.faker.paragraph(),
        }
