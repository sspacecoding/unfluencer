from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class MockUser:
    pk: int
    username: str
    full_name: str
    profile_pic_url: str

@dataclass
class MockComment:
    pk: int
    user: MockUser
    text: str
    created_at: datetime
    like_count: int

@dataclass
class MockMediaResource:
    thumbnail_url: str
    media_type: int

@dataclass
class MockMedia:
    pk: int
    code: str
    caption_text: str
    thumbnail_url: str
    resources: List[MockMediaResource]
    like_count: int
    comment_count: int
    taken_at: datetime
    user: MockUser

    def __getattr__(self, name):
        """Método para lidar com atributos dinâmicos"""
        if name == 'thumbnail_url':
            if self.resources and len(self.resources) > 0:
                return self.resources[0].thumbnail_url
            return self.thumbnail_url
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# Mock de usuário
MOCK_USER = MockUser(
    pk=123456789,
    username="usuario_teste",
    full_name="Usuário Teste",
    profile_pic_url="https://example.com/profile.jpg"
)

# Mock de comentários
MOCK_COMMENTS = [
    MockComment(
        pk=111111,
        user=MOCK_USER,
        text="Que post incrível! 👏",
        created_at=datetime.now(),
        like_count=5
    ),
    MockComment(
        pk=222222,
        user=MOCK_USER,
        text="Muito bom conteúdo!",
        created_at=datetime.now(),
        like_count=3
    ),
    MockComment(
        pk=333333,
        user=MOCK_USER,
        text="Adorei!",
        created_at=datetime.now(),
        like_count=1
    )
]

# Mock de post
MOCK_MEDIA = MockMedia(
    pk=987654321,
    code="ABC123",
    caption_text="Este é um post de teste para demonstrar o funcionamento dos mocks",
    thumbnail_url="https://example.com/image.jpg",
    resources=[
        MockMediaResource(
            thumbnail_url="https://segredosdomundo.r7.com/wp-content/uploads/2020/08/batatas-origem-tipos-e-utilidades-que-vao-alem-da-alimentacao-23.jpg",
            media_type=1
        )
    ],
    like_count=100,
    comment_count=50,
    taken_at=datetime.now(),
    user=MOCK_USER
)

class MockInstagramClient:
    def __init__(self, use_mocks=True):
        self.use_mocks = use_mocks
        self.media_id = MOCK_MEDIA.pk
        self.comments = MOCK_COMMENTS
        self._media_info = MOCK_MEDIA

    def media_pk_from_url(self, url: str) -> int:
        if self.use_mocks:
            return self.media_id
        raise NotImplementedError("Método não mockado")

    def media_info(self, media_id: int) -> MockMedia:
        if self.use_mocks:
            return self._media_info
        raise NotImplementedError("Método não mockado")

    def media_comments(self, media_id: int, amount: int = 10) -> List[MockComment]:
        if self.use_mocks:
            return self.comments[:amount]
        raise NotImplementedError("Método não mockado")

    def media_comment(self, media_id: int, text: str, replied_to_comment_id: Optional[int] = None) -> MockComment:
        if self.use_mocks:
            return MockComment(
                pk=999999,
                user=MOCK_USER,
                text=text,
                created_at=datetime.now(),
                like_count=0
            )
        raise NotImplementedError("Método não mockado")

    def get_timeline_feed(self):
        if self.use_mocks:
            return True
        raise NotImplementedError("Método não mockado")

    def login(self, username: str, password: str) -> bool:
        if self.use_mocks:
            return True
        raise NotImplementedError("Método não mockado")

    def load_settings(self, session_file: str):
        if self.use_mocks:
            return True
        raise NotImplementedError("Método não mockado")

    def dump_settings(self, session_file: str):
        if self.use_mocks:
            return True
        raise NotImplementedError("Método não mockado") 