"""User & Supplier Service - Business logic and DB operations."""

from typing import Optional

from beanie import PydanticObjectId

from shared.models.user import User, ContactInfo, UserProfile
from shared.models.supplier import (
    Supplier, SupplierContactInfo, CompanyInfo, CompanyAddress,
    BusinessInfo, BankingInfo,
)
from shared.errors import DuplicateError, NotFoundError
from utils.password import hash_password
from utils.datetime_utils import utc_now
from kafka.producer import get_kafka_producer
from shared.kafka.topics import EventType
from utils.serialization import oid_to_str


class UserService:
    """Handles user and supplier DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()

    # ----------------------------------------------------------------
    # User
    # ----------------------------------------------------------------

    async def create_user(
        self,
        email: str,
        password: str,
        display_name: str,
        phone: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> User:
        # TODO: Implement create_user
        # 1. Normalize email (lowercase, strip)
        # 2. Check for duplicate email using find_one
        # 3. Create User document with hashed password, ContactInfo, UserProfile
        # 4. Insert into MongoDB
        # 5. Emit USER_CREATED Kafka event
        # 6. Return the created user
        pass

    async def get_user(self, user_id: str) -> User:
        # TODO: Implement get_user
        # 1. Fetch user by ID using User.get()
        # 2. Handle invalid ObjectId (raise NotFoundError)
        # 3. Check user exists and is not soft-deleted
        # 4. Return the user
        pass

    async def list_users(self, skip: int = 0, limit: int = 20) -> list[User]:
        # TODO: Implement list_users
        # 1. Query for users where deleted_at is None
        # 2. Apply skip/limit pagination (cap limit at 100)
        # 3. Return the list
        pass

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        bio: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> User:
        # TODO: Implement update_user
        # 1. Fetch the user using get_user
        # 2. Update only the provided fields (display_name, phone, bio, avatar)
        # 3. Save the updated document
        # 4. Emit USER_UPDATED Kafka event
        # 5. Return the updated user
        pass

    async def delete_user(self, user_id: str) -> None:
        # TODO: Implement delete_user (soft delete)
        # 1. Fetch the user using get_user
        # 2. Set deleted_at to current UTC time
        # 3. Save the document
        # 4. Emit USER_DELETED Kafka event
        pass

    # ----------------------------------------------------------------
    # Supplier
    # ----------------------------------------------------------------

    async def create_supplier(self, body) -> Supplier:
        """Create a new supplier. `body` is a CreateSupplierRequest."""
        # TODO: Implement create_supplier
        # 1. Normalize email (lowercase, strip)
        # 2. Check for duplicate email using find_one
        # 3. Build SupplierContactInfo from body.contact_info
        # 4. Build CompanyAddress for business_address (and optionally shipping_address)
        # 5. Build CompanyInfo with legal_name, dba_name, and addresses
        # 6. Build BusinessInfo from body.business_info
        # 7. Build BankingInfo if provided
        # 8. Create Supplier document with hashed password and all info objects
        # 9. Insert into MongoDB
        # 10. Emit SUPPLIER_CREATED Kafka event
        # 11. Return the created supplier
        pass

    async def get_supplier(self, supplier_id: str) -> Supplier:
        # TODO: Implement get_supplier
        # 1. Fetch supplier by ID using Supplier.get()
        # 2. Handle invalid ObjectId (raise NotFoundError)
        # 3. Check supplier exists
        # 4. Return the supplier
        pass

    async def list_suppliers(self, skip: int = 0, limit: int = 20) -> list[Supplier]:
        # TODO: Implement list_suppliers
        # 1. Query all suppliers using find_all()
        # 2. Apply skip/limit pagination (cap limit at 100)
        # 3. Return the list
        pass

    async def update_supplier(
        self,
        supplier_id: str,
        primary_phone: Optional[str] = None,
        legal_name: Optional[str] = None,
        dba_name: Optional[str] = None,
        support_email: Optional[str] = None,
        support_phone: Optional[str] = None,
    ) -> Supplier:
        # TODO: Implement update_supplier
        # 1. Fetch the supplier using get_supplier
        # 2. Update only the provided fields on the appropriate nested objects
        # 3. Save the updated document
        # 4. Emit SUPPLIER_UPDATED Kafka event
        # 5. Return the updated supplier
        pass

    async def delete_supplier(self, supplier_id: str) -> None:
        # TODO: Implement delete_supplier (hard delete)
        # 1. Fetch the supplier using get_supplier
        # 2. Delete the document from MongoDB
        # 3. Emit SUPPLIER_DELETED Kafka event
        pass
