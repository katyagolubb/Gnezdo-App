import asyncio
import json
import tempfile
import os
from unittest import TestCase
from unittest.mock import patch, AsyncMock, MagicMock

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from fastapi import HTTPException

from main import (
    add_diversity,
    get_recommendations,
    compute_recommendations_task,
    get_user_books,
    get_all_books,
    precompute_matrices,
    collaborative_filtering,
    content_filtering,
)


class RecommendationsApiTest(TestCase):
    """
    Тесты поведения эндпоинта рекомендаций (F_Rec_1–F_Rec_3)
    через прямой вызов функции get_recommendations без HTTP-уровня.
    """

    def setUp(self):
        self.user_id = 1
        self.token = "fake-jwt-token"

    @patch("main.redis_client_async")
    @patch("main.compute_recommendations_task")
    def test_get_recommendations_personalized_for_user_with_books(
        self,
        mock_task,
        mock_redis,
    ):
        """
        F_Rec_1, F_Rec_2:
        - для пользователя с книгами возвращается непустой персональный список.
        """
        # кэш пустой
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        # Результат фоновой задачи
        task_instance = MagicMock()
        task_instance.get.return_value = {
            "recommendations": [
                {
                    "book_id": 10,
                    "name": "Book A",
                    "author": "Author A",
                    "genres": ["Fantasy"],
                    "reason": "Matches your interests",
                }
            ]
        }
        mock_task.delay.return_value = task_instance

        result = asyncio.run(
            get_recommendations(user_id=self.user_id, current_user_id=self.user_id, token=self.token)
        )

        self.assertIn("recommendations", result)
        self.assertGreaterEqual(len(result["recommendations"]), 1)
        self.assertEqual(result["recommendations"][0]["book_id"], 10)

    @patch("main.redis_client_async")
    def test_get_recommendations_from_cache(self, mock_redis):
        """
        F_Rec_1:
        - при наличии кэша результат берётся из Redis без фоновой задачи.
        """
        cached_value = {"recommendations": [{"book_id": 5, "name": "Cached Book"}]}
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_value))

        result = asyncio.run(
            get_recommendations(user_id=self.user_id, current_user_id=self.user_id, token=self.token)
        )

        self.assertEqual(result, cached_value)

    def test_get_recommendations_for_other_user_forbidden(self):
        """
        F_Rec_1:
        - пользователь не может запросить рекомендации для другого user_id.
        """
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                get_recommendations(user_id=1, current_user_id=2, token=self.token)
            )
        self.assertEqual(ctx.exception.status_code, 403)


class ComputeRecommendationsTaskLogicTest(TestCase):
    """
    Юнит-тесты логики фоновой задачи (F_Rec_2, F_Rec_3).
    Проверяем поведение при наличии/отсутствии книг пользователя.
    """

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    def test_recommendations_for_user_without_books_returns_popular(
        self,
        mock_requests_get,
        mock_redis,
    ):
        """
        F_Rec_3:
        - если у пользователя нет книг, возвращаются популярные (случайные) книги.
        """
        from main import compute_recommendations_task

        # Redis кэш пустой
        mock_redis.get.return_value = None

        # Первая выборка — книги пользователя (пустой список)
        user_books_response = MagicMock()
        user_books_response.status_code = 200
        user_books_response.json.return_value = {"results": []}

        # Вторая выборка — все доступные книги
        all_books_response = MagicMock()
        all_books_response.status_code = 200
        all_books_response.json.return_value = {
            "results": [
                {
                    "user_book_id": 1,
                    "book": {
                        "book_id": 100,
                        "name": "Popular Book",
                        "author": "Author",
                        "overview": "Desc",
                        "genres": ["Fantasy"],
                    },
                }
            ],
            "next": None,
        }

        mock_requests_get.side_effect = [
            user_books_response,
            all_books_response,
        ]

        result = compute_recommendations_task.run(user_id=1, token="token")

        self.assertIn("recommendations", result)
        self.assertGreaterEqual(len(result["recommendations"]), 1)
        # причина рекомендаций для пользователя без книг — популярность
        self.assertEqual(result["recommendations"][0]["reason"], "Popular book")


class AddDiversityTest(TestCase):
    """
    Тесты функции add_diversity, которая дополняет рекомендации разнообразными книгами.
    Это часть F_Rec_1 (персонализированный, но разнообразный список).
    """

    def test_add_diversity_does_not_duplicate_books(self):
        recommendations = [
            {
                "book_id": 1,
                "name": "Base Rec",
                "genres": ["Fantasy"],
                "reason": "Matches your interests",
                "similarity": 0.9,
            }
        ]
        all_books = [
            {
                "user_book_id": 10,
                "book": {
                    "book_id": 1,
                    "name": "Base Rec",
                    "genres": ["Fantasy"],
                    "overview": "",
                },
            },
            {
                "user_book_id": 11,
                "book": {
                    "book_id": 2,
                    "name": "Extra Book",
                    "genres": ["Fantasy"],
                    "overview": "",
                },
            },
        ]
        user_books = [
            {
                "user_book_id": 12,
                "book": {
                    "book_id": 3,
                    "name": "User Book",
                    "genres": ["Fantasy"],
                    "overview": "",
                },
            }
        ]

        result = add_diversity(recommendations, all_books, user_books)

        # Книга 2 добавлена, книга 1 не продублирована
        ids = [r["book_id"] for r in result]
        self.assertIn(1, ids)
        self.assertIn(2, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_add_diversity_returns_unchanged_when_five_or_more(self):
        """Когда рекомендаций >= 5, функция возвращает их без изменений."""
        recs = [{"book_id": i, "name": f"Book{i}", "genres": ["Fiction"], "reason": "x", "similarity": 0.5} for i in range(5)]
        all_books = []
        user_books = []
        result = add_diversity(recs, all_books, user_books)
        self.assertEqual(len(result), 5)
        self.assertEqual(result, recs)

    def test_add_diversity_empty_available_books_returns_unchanged(self):
        """При пустом списке доступных книг возвращаются исходные рекомендации."""
        recs = [{"book_id": 1, "name": "B1", "genres": ["Fiction"], "reason": "x", "similarity": 0.5}]
        all_books = [{"user_book_id": 1, "book": {"book_id": 1, "name": "B1", "genres": ["Fiction"], "overview": ""}}]
        user_books = [{"user_book_id": 2, "book": {"book_id": 1, "genres": ["Fiction"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["book_id"], 1)

    def test_add_diversity_adds_common_genre_books(self):
        """Добавляются книги с общими жанрами пользователя."""
        recs = [{"book_id": 1, "name": "B1", "genres": ["Fantasy"], "reason": "x", "similarity": 0.5}]
        all_books = [
            {"user_book_id": 10, "book": {"book_id": 1, "name": "B1", "genres": ["Fantasy"], "overview": ""}},
            {"user_book_id": 11, "book": {"book_id": 2, "name": "B2", "genres": ["Fantasy"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 12, "book": {"book_id": 3, "genres": ["Fantasy"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertGreaterEqual(len(result), 2)
        self.assertTrue(any(r["book_id"] == 2 for r in result))

    def test_add_diversity_max_five_results(self):
        """Результат содержит не более 5 книг."""
        recs = []
        all_books = [
            {"user_book_id": i, "book": {"book_id": i, "name": f"B{i}", "genres": ["Fantasy"], "overview": ""}}
            for i in range(10)
        ]
        user_books = []
        result = add_diversity(recs, all_books, user_books)
        self.assertLessEqual(len(result), 5)

    def test_add_diversity_handles_unknown_genres(self):
        """Корректно обрабатывает Unknown в жанрах."""
        recs = [{"book_id": 1, "name": "B1", "genres": ["Fantasy"], "reason": "x", "similarity": 0.5}]
        all_books = [
            {"user_book_id": 10, "book": {"book_id": 1, "name": "B1", "genres": ["Fantasy"], "overview": ""}},
            {"user_book_id": 11, "book": {"book_id": 2, "name": "B2", "genres": ["Unknown"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 12, "book": {"book_id": 3, "genres": ["Fantasy"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertGreaterEqual(len(result), 1)

    def test_add_diversity_empty_recommendations_adds_from_available(self):
        """При пустых рекомендациях добавляются книги из доступных."""
        recs = []
        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B10", "genres": ["Sci-Fi"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 2, "book": {"book_id": 99, "genres": ["Sci-Fi"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["book_id"], 10)

    def test_add_diversity_explore_new_genre_reason(self):
        """Для книг новых жанров формируется reason Explore a new genre."""
        recs = [{"book_id": 1, "name": "B1", "genres": ["Fantasy"], "reason": "x", "similarity": 0.5}]
        all_books = [
            {"user_book_id": 10, "book": {"book_id": 1, "name": "B1", "genres": ["Fantasy"], "overview": ""}},
            {"user_book_id": 11, "book": {"book_id": 2, "name": "B2", "genres": ["Sci-Fi"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 12, "book": {"book_id": 3, "genres": ["Fantasy"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        explore_reasons = [r for r in result if "Explore a new genre" in r.get("reason", "")]
        self.assertGreaterEqual(len(explore_reasons), 0)

    def test_add_diversity_because_you_like_reason(self):
        """Для книг с общими жанрами формируется reason Because you like."""
        recs = []
        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B10", "genres": ["Fantasy"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 2, "book": {"book_id": 99, "genres": ["Fantasy"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertEqual(len(result), 1)
        self.assertIn("Because you like", result[0]["reason"])


class ComputeRecommendationsTaskExtraTest(TestCase):
    """Дополнительные тесты compute_recommendations_task."""

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    def test_empty_all_books_returns_empty_recommendations(self, mock_get, mock_redis):
        """При отсутствии книг возвращается пустой список."""
        mock_redis.get.return_value = None
        user_books_resp = MagicMock()
        user_books_resp.status_code = 200
        user_books_resp.json.return_value = {"results": []}
        all_books_resp = MagicMock()
        all_books_resp.status_code = 200
        all_books_resp.json.return_value = {"results": [], "next": None}
        mock_get.side_effect = [user_books_resp, all_books_resp]

        result = compute_recommendations_task.run(user_id=1, token="t")
        self.assertEqual(result["recommendations"], [])

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    def test_user_books_from_cache(self, mock_get, mock_redis):
        """Используется кэш при наличии user_books в Redis."""
        cached_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}]
        mock_redis.get.side_effect = [
            json.dumps(cached_books),
            None,
        ]
        all_books_resp = MagicMock()
        all_books_resp.status_code = 200
        all_books_resp.json.return_value = {
            "results": [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}],
            "next": None,
        }
        mock_get.return_value = all_books_resp

        with patch("main.collaborative_filtering", return_value=[]):
            with patch("main.content_filtering") as mock_cf:
                mock_cf.return_value = []
                result = compute_recommendations_task.run(user_id=1, token="t")
        self.assertIn("recommendations", result)

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    @patch("main.content_filtering")
    @patch("main.collaborative_filtering")
    def test_user_with_books_uses_collaborative_and_content(
        self, mock_collab, mock_content, mock_get, mock_redis
    ):
        """При наличии книг вызываются collaborative и content filtering."""
        mock_redis.get.return_value = None
        user_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}]
        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}},
            {"user_book_id": 2, "book": {"book_id": 20, "name": "B2", "genres": ["F"], "overview": ""}},
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"results": user_books})),
            MagicMock(status_code=200, json=MagicMock(return_value={"results": all_books, "next": None})),
        ]
        mock_collab.return_value = [20]
        mock_content.return_value = [{"book_id": 20, "name": "B2", "author": "A", "overview": "", "genres": ["F"], "reason": "x", "similarity": 0.8}]

        result = compute_recommendations_task.run(user_id=1, token="t")
        mock_collab.assert_called_once()
        mock_content.assert_called_once()
        self.assertIn("recommendations", result)
        self.assertEqual(len(result["recommendations"]), 1)

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    @patch("main.content_filtering")
    @patch("main.collaborative_filtering")
    def test_recommendations_reason_includes_common_genres(self, mock_collab, mock_content, mock_get, mock_redis):
        """Рекомендации с общими жанрами содержат Genres в reason."""
        mock_redis.get.return_value = None
        user_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["Fantasy"], "overview": ""}}]
        all_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["Fantasy"], "overview": ""}}]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"results": user_books})),
            MagicMock(status_code=200, json=MagicMock(return_value={"results": all_books, "next": None})),
        ]
        mock_collab.return_value = [20]
        mock_content.return_value = [{
            "book_id": 20, "name": "B2", "author": "A", "overview": "",
            "genres": ["Fantasy", "Adventure"], "reason": "x", "similarity": 0.9
        }]

        result = compute_recommendations_task.run(user_id=1, token="t")
        self.assertIn("recommendations", result)
        self.assertIn("Genres:", result["recommendations"][0]["reason"])

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    def test_all_books_from_cache(self, mock_get, mock_redis):
        """all_books берётся из кэша при наличии."""
        cached_all = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}]
        mock_redis.get.side_effect = [
            None,
            json.dumps(cached_all),
        ]
        user_books_resp = MagicMock()
        user_books_resp.status_code = 200
        user_books_resp.json.return_value = {"results": []}
        mock_get.return_value = user_books_resp

        result = compute_recommendations_task.run(user_id=1, token="t")
        self.assertIn("recommendations", result)
        self.assertEqual(len(result["recommendations"]), 1)

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    @patch("main.add_diversity")
    def test_add_diversity_called_with_recommendations(self, mock_add_div, mock_get, mock_redis):
        """add_diversity вызывается для дополнения рекомендаций."""
        mock_redis.get.return_value = None
        user_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}]
        all_books = [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["F"], "overview": ""}}]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"results": user_books})),
            MagicMock(status_code=200, json=MagicMock(return_value={"results": all_books, "next": None})),
        ]
        mock_add_div.side_effect = lambda recs, ab, ub: recs

        with patch("main.collaborative_filtering", return_value=[]):
            with patch("main.content_filtering", return_value=[]):
                compute_recommendations_task.run(user_id=1, token="t")
        mock_add_div.assert_called_once()


class GetRecommendationsExtraTest(TestCase):
    """Дополнительные тесты get_recommendations."""

    @patch("main.redis_client_async")
    @patch("main.compute_recommendations_task")
    def test_task_exception_raises_500(self, mock_task, mock_redis):
        """При исключении в задаче возвращается 500."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_task.delay.return_value.get.side_effect = Exception("Task failed")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(get_recommendations(user_id=1, current_user_id=1, token="t"))
        self.assertEqual(ctx.exception.status_code, 500)

    @patch("main.redis_client_async")
    @patch("main.compute_recommendations_task")
    def test_empty_recommendations_returned(self, mock_task, mock_redis):
        """Корректно обрабатывается пустой список рекомендаций."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_task.delay.return_value.get.return_value = {"recommendations": []}

        result = asyncio.run(get_recommendations(user_id=1, current_user_id=1, token="t"))
        self.assertEqual(result["recommendations"], [])

    @patch("main.redis_client_async")
    @patch("main.compute_recommendations_task")
    def test_redis_setex_called_after_task(self, mock_task, mock_redis):
        """Redis setex вызывается после успешного выполнения задачи."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_task.delay.return_value.get.return_value = {"recommendations": [{"book_id": 1}]}

        asyncio.run(get_recommendations(user_id=1, current_user_id=1, token="t"))
        mock_redis.setex.assert_called_once()

    @patch("main.redis_client_async")
    def test_cache_returns_without_task_call(self, mock_redis):
        """При наличии кэша задача не вызывается."""
        cached = {"recommendations": [{"book_id": 5}]}
        mock_redis.get = AsyncMock(return_value=json.dumps(cached))

        with patch("main.compute_recommendations_task") as mock_task:
            result = asyncio.run(get_recommendations(user_id=1, current_user_id=1, token="t"))
            mock_task.delay.assert_not_called()
        self.assertEqual(result, cached)


class FastAPIAppTest(TestCase):
    """Тесты FastAPI приложения."""

    def test_app_exists(self):
        """Приложение FastAPI создано."""
        from main import app
        self.assertIsNotNone(app)

    def test_app_has_routes(self):
        """У приложения есть маршруты."""
        from main import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        self.assertIn("/api/recommendations/", routes)
        self.assertIn("/api/precompute/", routes)

    def test_config_vars_exist(self):
        """Конфигурационные переменные заданы."""
        import main
        self.assertTrue(hasattr(main, "JWT_SECRET_KEY"))
        self.assertTrue(hasattr(main, "BASE_API_URL"))
        self.assertIsInstance(main.BASE_API_URL, str)


class GetUserBooksTest(TestCase):
    """Тесты get_user_books."""

    @patch("main.redis_client_async")
    def test_returns_from_cache(self, mock_redis):
        """При наличии кэша возвращает данные из Redis."""
        cached = [{"user_book_id": 1, "book": {"book_id": 10}}]
        mock_redis.get = AsyncMock(return_value=json.dumps(cached))

        result = asyncio.run(get_user_books(user_id=1, token="t"))
        self.assertEqual(result, cached)
        mock_redis.get.assert_called_once()

    @patch("main.redis_client_async")
    @patch("main.requests.get")
    def test_fetches_from_api_when_cache_empty(self, mock_get, mock_redis):
        """При пустом кэше запрашивает API."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"results": [{"book_id": 1}]})
        )

        result = asyncio.run(get_user_books(user_id=1, token="t"))
        self.assertEqual(result, [{"book_id": 1}])
        mock_get.assert_called_once()
        mock_redis.setex.assert_called_once()

    @patch("main.redis_client_async")
    @patch("main.requests.get")
    def test_returns_empty_on_api_error(self, mock_get, mock_redis):
        """При статусе != 200 возвращает пустой список."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_get.return_value = MagicMock(status_code=500)

        result = asyncio.run(get_user_books(user_id=1, token="t"))
        self.assertEqual(result, [])


class GetAllBooksTest(TestCase):
    """Тесты get_all_books."""

    @patch("main.redis_client_async")
    def test_returns_from_cache(self, mock_redis):
        """При наличии кэша возвращает данные."""
        cached = [{"book": {"book_id": 1}}]
        mock_redis.get = AsyncMock(return_value=json.dumps(cached))

        result = asyncio.run(get_all_books(token="t", user_id=1))
        self.assertEqual(result, cached)

    @patch("main.redis_client_async")
    @patch("main.requests.get")
    def test_fetches_with_pagination(self, mock_get, mock_redis):
        """Поддерживает пагинацию next."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={
                "results": [{"book": {"book_id": 1}}],
                "next": "http://next"
            })),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "results": [{"book": {"book_id": 2}}],
                "next": None
            })),
        ]

        result = asyncio.run(get_all_books(token="t", user_id=1))
        self.assertEqual(len(result), 2)
        self.assertEqual(mock_get.call_count, 2)

    @patch("main.redis_client_async")
    @patch("main.requests.get")
    def test_raises_on_api_error(self, mock_get, mock_redis):
        """Вызывает HTTPException при status != 200."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_get.return_value = MagicMock(status_code=500)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(get_all_books(token="t", user_id=1))
        self.assertEqual(ctx.exception.status_code, 500)


class PrecomputeMatricesTest(TestCase):
    """Тесты precompute_matrices."""

    @patch("main.requests.post")
    @patch("main.requests.get")
    def test_success_creates_joblib_files(self, mock_get, mock_post):
        """Успешно создаёт joblib файлы."""
        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B1", "author": "A1", "overview": "O1", "genres": ["F"]}},
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"results": all_books})),
        ]
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"1": 100}))

        with tempfile.TemporaryDirectory() as tmp:
            with patch("main.dump") as mock_dump:
                with patch("os.getcwd", return_value=tmp):
                    precompute_matrices(token="t")
        mock_get.assert_called()
        mock_post.assert_called_once()

    @patch("main.requests.get")
    def test_raises_when_no_books(self, mock_get):
        """Вызывает HTTPException при отсутствии книг."""
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"results": []}))

        with self.assertRaises(HTTPException) as ctx:
            precompute_matrices(token="t")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No books", ctx.exception.detail)

    @patch("main.requests.get")
    def test_raises_on_failed_fetch(self, mock_get):
        """Вызывает HTTPException при ошибке API."""
        mock_get.return_value = MagicMock(status_code=500)

        with self.assertRaises(HTTPException) as ctx:
            precompute_matrices(token="t")
        self.assertEqual(ctx.exception.status_code, 500)

    @patch("main.requests.post")
    @patch("main.requests.get")
    def test_raises_on_owners_fetch_failure(self, mock_get, mock_post):
        """Вызывает HTTPException при ошибке получения owners."""
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={
            "results": [{"user_book_id": 1, "book": {"book_id": 10, "name": "B", "author": "A", "overview": "O", "genres": ["F"]}}]
        }))
        mock_post.return_value = MagicMock(status_code=500)

        with self.assertRaises(HTTPException) as ctx:
            precompute_matrices(token="t")
        self.assertEqual(ctx.exception.status_code, 500)


class CollaborativeFilteringTest(TestCase):
    """Тесты collaborative_filtering."""

    def test_returns_empty_on_file_not_found(self):
        """Возвращает [] при отсутствии файла."""
        with patch("main.load") as mock_load:
            mock_load.side_effect = FileNotFoundError
            result = collaborative_filtering(user_id=1, user_books=[{"book": {"book_id": 1, "genres": []}}])
        self.assertEqual(result, [])

    def test_returns_empty_when_user_not_in_matrix(self):
        """Возвращает [] если user_id нет в матрице."""
        with patch("main.load") as mock_load:
            mock_load.return_value = (["2", "3"], [10, 20], np.zeros((2, 2)))
            result = collaborative_filtering(user_id=1, user_books=[{"book": {"book_id": 1, "genres": []}}])
        self.assertEqual(result, [])

    def test_returns_recommendations_with_valid_joblib(self):
        """Возвращает рекомендации при наличии валидных joblib файлов."""
        user_ids = ["1", "2"]
        book_ids = [10, 20]
        matrix = np.array([[1, 0], [0, 1]])
        books_df = pd.DataFrame({
            "book_id": [10, 20],
            "name": ["B1", "B2"],
            "author": ["A1", "A2"],
            "overview": ["O1", "O2"],
            "genres": [["Fantasy"], ["Sci-Fi"]]
        })
        def load_side_effect(path):
            p = str(path) if path else ""
            if "user_book" in p:
                return (user_ids, book_ids, matrix)
            return books_df

        with patch("main.joblib.load", side_effect=load_side_effect):
            with patch("main.load", side_effect=load_side_effect):
                user_books = [{"book": {"book_id": 10, "genres": ["Fantasy"], "overview": ""}}]
                result = collaborative_filtering(user_id=1, user_books=user_books)
        self.assertIsInstance(result, list)


class ContentFilteringTest(TestCase):
    """Тесты content_filtering."""

    def test_returns_empty_for_empty_candidates(self):
        """Возвращает [] для пустого списка кандидатов."""
        with patch("main.joblib.load") as mock_load:
            books_df = pd.DataFrame({"book_id": [1], "name": ["B"], "author": ["A"], "overview": [""], "genres": [["F"]]})
            mock_load.side_effect = [
                np.array([[1.0]]),
                MagicMock(transform=MagicMock(return_value=np.array([[1.0]]))),
                books_df,
            ]
            result = content_filtering([{"book": {"book_id": 1, "genres": ["F"], "overview": ""}}], [999])
        self.assertEqual(result, [])

    def test_returns_recommendations_with_mocked_joblib(self):
        """Возвращает рекомендации при корректных данных."""
        books_df = pd.DataFrame({
            "book_id": [10, 20],
            "name": ["B1", "B2"],
            "author": ["A1", "A2"],
            "overview": ["O1", "O2"],
            "genres": [["Fantasy"], ["Sci-Fi"]]
        })
        corpus = ["Fantasy O1", "Sci-Fi O2"]
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform(corpus)

        with patch("main.joblib.load") as mock_load:
            mock_load.side_effect = [tfidf, vectorizer, books_df]
            result = content_filtering(
                [{"book": {"book_id": 10, "genres": ["Fantasy"], "overview": "O1"}}],
                [10, 20]
            )
        self.assertGreaterEqual(len(result), 1)
        self.assertIn("book_id", result[0])
        self.assertIn("reason", result[0])

    def test_handles_nan_overview(self):
        """Корректно обрабатывает NaN в overview."""
        books_df = pd.DataFrame({
            "book_id": [10],
            "name": ["B1"],
            "author": ["A1"],
            "overview": [""],
            "genres": [["Fantasy"]]
        })
        corpus = ["Fantasy magic"]
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform(corpus)

        with patch("main.joblib.load") as mock_load:
            mock_load.side_effect = [tfidf, vectorizer, books_df]
            result = content_filtering(
                [{"book": {"book_id": 10, "genres": ["Fantasy"], "overview": ""}}],
                [10]
            )
        self.assertEqual(len(result), 1)

    def test_returns_empty_for_empty_candidates_after_filter(self):
        """Возвращает [] когда candidates пуст после фильтрации."""
        books_df = pd.DataFrame({"book_id": [1], "name": ["B"], "author": ["A"], "overview": ["desc"], "genres": [["F"]]})
        vec = TfidfVectorizer()
        tfidf = vec.fit_transform(["Fantasy desc"])
        with patch("main.joblib.load") as mock_load:
            mock_load.side_effect = [tfidf, vec, books_df]
            result = content_filtering([{"book": {"book_id": 1, "genres": ["F"], "overview": "desc"}}], [999])
        self.assertEqual(result, [])


class ComputeTaskSyncAllBooksErrorTest(TestCase):
    """Тест ошибки sync_get_all_books в compute_recommendations_task."""

    @patch("main.redis_client_sync")
    @patch("main.requests.get")
    def test_raises_on_all_books_fetch_failure(self, mock_get, mock_redis):
        """При ошибке получения all_books выбрасывается HTTPException."""
        mock_redis.get.return_value = None
        mock_get.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"results": [{"user_book_id": 1, "book": {"book_id": 10, "genres": ["F"], "overview": ""}}]})),
            MagicMock(status_code=500),
        ]

        with self.assertRaises(HTTPException) as ctx:
            compute_recommendations_task.run(user_id=1, token="t")
        self.assertEqual(ctx.exception.status_code, 500)


class AddDiversityExploreDifferentBookTest(TestCase):
    """Тесты add_diversity — ветка Explore a different book."""

    def test_explore_different_book_reason_for_unknown_genre(self):
        """При Unknown в жанрах формируется reason Explore a different book."""
        recs = []
        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B", "genres": ["Unknown"], "overview": ""}},
        ]
        user_books = [{"user_book_id": 2, "book": {"book_id": 99, "genres": ["Fantasy"], "overview": ""}}]
        result = add_diversity(recs, all_books, user_books)
        self.assertEqual(len(result), 1)
        self.assertIn("Explore a different book", result[0]["reason"])


class PrecomputeEndpointTest(TestCase):
    """Тесты эндпоинта /api/precompute/."""

    def test_rejects_invalid_auth_header(self):
        """Отклоняет неверный Authorization header."""
        try:
            from fastapi.testclient import TestClient
            from main import app
        except ImportError:
            self.skipTest("httpx required for TestClient")
            return

        client = TestClient(app)
        resp = client.get("/api/precompute/", headers={"Authorization": "Invalid xxx"})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_missing_bearer_prefix(self):
        """Отклоняет заголовок без Bearer."""
        try:
            from fastapi.testclient import TestClient
            from main import app
        except ImportError:
            self.skipTest("httpx required for TestClient")
            return

        client = TestClient(app)
        resp = client.get("/api/precompute/", headers={"Authorization": "Basic xxx"})
        self.assertEqual(resp.status_code, 401)

    @patch("main.requests.post")
    @patch("main.requests.get")
    def test_precompute_success_with_mocked_api(self, mock_get, mock_post):
        """precompute успешно выполняется при корректных ответах API."""
        try:
            from fastapi.testclient import TestClient
            from main import app
        except ImportError:
            self.skipTest("httpx required for TestClient")
            return

        all_books = [
            {"user_book_id": 1, "book": {"book_id": 10, "name": "B1", "author": "A1", "overview": "O1", "genres": ["F"]}},
        ]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={
            "results": all_books,
            "next": None
        }))
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"1": 100}))

        client = TestClient(app)
        resp = client.get("/api/precompute/", headers={"Authorization": "Bearer any-token"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("message", resp.json())


class RecommendationsEndpointAuthTest(TestCase):
    """Тесты аутентификации эндпоинта recommendations."""

    def test_recommendations_requires_auth(self):
        """Эндпоинт /api/recommendations/ требует аутентификацию."""
        try:
            from fastapi.testclient import TestClient
            from main import app
        except ImportError:
            self.skipTest("httpx required for TestClient")
            return

        client = TestClient(app)
        resp = client.get("/api/recommendations/?user_id=1")
        self.assertIn(resp.status_code, [401, 403])


class AuthDependenciesTest(TestCase):
    """Тесты зависимостей аутентификации."""

    def test_get_current_user_id_invalid_token(self):
        """get_current_user_id отклоняет невалидный токен."""
        import main
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(main.get_current_user_id(token="invalid-token"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_current_user_id_valid_token(self):
        """get_current_user_id возвращает user_id из валидного JWT."""
        import main
        import jwt
        token = jwt.encode(
            {"user_id": 42},
            main.JWT_SECRET_KEY,
            algorithm=main.JWT_ALGORITHM
        )
        result = asyncio.run(main.get_current_user_id(token=token))
        self.assertEqual(result, 42)

    def test_get_current_user_id_missing_user_id(self):
        """get_current_user_id отклоняет токен без user_id."""
        import main
        import jwt
        token = jwt.encode({}, main.JWT_SECRET_KEY, algorithm=main.JWT_ALGORITHM)
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(main.get_current_user_id(token=token))
        self.assertEqual(ctx.exception.status_code, 401)


class ShutdownEventTest(TestCase):
    """Тест shutdown event."""

    @patch("main.redis_client_async")
    def test_shutdown_closes_redis(self, mock_redis):
        """shutdown_event закрывает Redis соединение."""
        from main import shutdown_event
        mock_redis.close = AsyncMock()
        asyncio.run(shutdown_event())
        mock_redis.close.assert_called_once()

