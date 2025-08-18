# services/database.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Dict, List, Optional
from bson import ObjectId
from datetime import datetime
import logging
from config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """MongoDB Datenbankservice mit vektorbasierter Berufssuche"""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.users_col: Optional[AsyncIOMotorCollection] = None
        self.occupations_col: Optional[AsyncIOMotorCollection] = None
        self.feedback_col: Optional[AsyncIOMotorCollection] = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(settings.mongo_uri)
            await self.client.server_info()
            logger.info("Erfolgreich mit MongoDB verbunden")

            self.db = self.client[settings.database_name]
            self.users_col = self.db[settings.users_collection]
            self.occupations_col = self.db[settings.occupations_collection]
            self.feedback_col = self.db[settings.feedback_collection]

            await self._create_indexes()

            count = await self.occupations_col.count_documents({})
            logger.info(f"{count} Berufe in der Datenbank gefunden")

        except Exception as e:
            logger.error(f"Verbindung zu MongoDB fehlgeschlagen: {e}")
            raise

    async def disconnect(self):
        if self.client:
            self.client.close()
            logger.info("Von MongoDB getrennt")

    async def _create_indexes(self):
        try:
            await self.users_col.create_index("username", unique=True)
            await self.users_col.create_index("last_login")
            await self.feedback_col.create_index("user_id")
            await self.feedback_col.create_index("created_at")
            logger.info("Indizes für Benutzer und Feedback erstellt")
        except Exception as e:
            logger.warning(f"Einige Indizes existieren möglicherweise bereits: {e}")

    # ---------------- Benutzeroperationen ----------------
    async def create_user(self, user_data: Dict) -> str:
        try:
            result = await self.users_col.insert_one(user_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Benutzer konnte nicht erstellt werden: {e}")
            raise

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        try:
            user = await self.users_col.find_one({"username": username})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except Exception as e:
            logger.error(f"Benutzer konnte nicht über Benutzername gefunden werden: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        try:
            user = await self.users_col.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except Exception as e:
            logger.error(f"Benutzer konnte nicht über ID gefunden werden: {e}")
            return None

    async def update_user_login(self, user_id: str) -> bool:
        try:
            result = await self.users_col.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Benutzer-Login konnte nicht aktualisiert werden: {e}")
            return False

    async def update_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        try:
            result = await self.users_col.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"preferences": preferences}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Benutzereinstellungen konnten nicht aktualisiert werden: {e}")
            return False

    # ---------------- Vektorbasierte Berufssuche ----------------
    async def vector_search_occupations(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        Suche nach Top-N Berufen mittels Vektorähnlichkeit (Kosinus-Ähnlichkeit).
        Gibt [{"message": "couldn't found"}] zurück, wenn keine Übereinstimmungen gefunden werden.
        """
        try:
            pipeline = [
                {"$match": {"embedding": {"$exists": True, "$ne": None}}},
                {"$addFields": {
                    "similarity": {
                        "$let": {
                            "vars": {
                                "dotProduct": {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": "$embedding"}]},
                                        "initialValue": 0,
                                        "in": {"$add": ["$$value", {"$multiply": [
                                            {"$arrayElemAt": ["$embedding", "$$this"]},
                                            {"$arrayElemAt": [query_embedding, "$$this"]}
                                        ]}]}
                                    }
                                },
                                "queryMagnitude": {"$sqrt": {"$reduce": {"input": query_embedding, "initialValue": 0, "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}}}},
                                "docMagnitude": {"$sqrt": {"$reduce": {"input": "$embedding", "initialValue": 0, "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}}}}
                            },
                            "in": {"$divide": ["$$dotProduct", {"$multiply": ["$$queryMagnitude", "$$docMagnitude"]}]}
                        }
                    }
                }},
                {"$match": {"similarity": {"$gte": 0.1}}},
                {"$sort": {"similarity": -1}},
                {"$limit": limit},
                {"$project": {
                    "name": 1,
                    "alternative_labels": 1,
                    "esco_code": 1,
                    "description": 1,
                    "essential_skills": 1,
                    "optional_skills": 1,
                    "score": "$similarity"
                }}
            ]

            results = []
            async for doc in self.occupations_col.aggregate(pipeline):
                doc["_id"] = str(doc["_id"])
                doc.setdefault("alternative_labels", [])
                doc.setdefault("essential_skills", [])
                doc.setdefault("optional_skills", [])
                doc.setdefault("description", "")
                results.append(doc)

            if not results:
                return [{"message": "couldn't found"}]

            return results

        except Exception as e:
            logger.error(f"Vektorsuche fehlgeschlagen: {e}")
            return [{"message": "couldn't found"}]

    # ---------------- Feedback-Operationen ----------------
    async def save_feedback(self, feedback_data: Dict) -> str:
        try:
            result = await self.feedback_col.insert_one(feedback_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Feedback konnte nicht gespeichert werden: {e}")
            raise

    async def get_user_feedback_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        try:
            cursor = self.feedback_col.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"Feedback-Verlauf konnte nicht abgerufen werden: {e}")
            return []


# Globale Instanz
db_service = DatabaseService()
