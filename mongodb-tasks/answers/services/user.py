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
        email = email.lower().strip()
        existing = await User.find_one({"contact_info.primary_email": email})
        if existing:
            raise DuplicateError("Email already in use")

        user = User(
            password_hash=hash_password(password),
            contact_info=ContactInfo(primary_email=email, phone=phone),
            profile=UserProfile(display_name=display_name, bio=bio),
        )
        await user.insert()

        self._kafka.emit(
            event_type=EventType.USER_CREATED,
            entity_id=oid_to_str(user.id),
            data=user.model_dump(mode="json"),
        )
        return user

    async def get_user(self, user_id: str) -> User:
        try:
            user = await User.get(PydanticObjectId(user_id))
        except Exception:
            raise NotFoundError("User not found")
        if not user or user.deleted_at:
            raise NotFoundError("User not found")
        return user

    async def list_users(self, skip: int = 0, limit: int = 20) -> list[User]:
        return (
            await User.find({"deleted_at": None})
            .skip(skip)
            .limit(min(limit, 100))
            .to_list()
        )

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        bio: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> User:
        user = await self.get_user(user_id)

        if display_name is not None:
            user.profile.display_name = display_name
        if phone is not None:
            user.contact_info.phone = phone
        if bio is not None:
            user.profile.bio = bio
        if avatar is not None:
            user.profile.avatar = avatar

        await user.save()

        self._kafka.emit(
            event_type=EventType.USER_UPDATED,
            entity_id=oid_to_str(user.id),
            data=user.model_dump(mode="json"),
        )
        return user

    async def delete_user(self, user_id: str) -> None:
        user = await self.get_user(user_id)
        user.deleted_at = utc_now()
        await user.save()

        self._kafka.emit(
            event_type=EventType.USER_DELETED,
            entity_id=oid_to_str(user.id),
            data={"user_id": oid_to_str(user.id)},
        )

    # ----------------------------------------------------------------
    # Supplier
    # ----------------------------------------------------------------

    async def create_supplier(self, body) -> Supplier:
        """Create a new supplier. `body` is a CreateSupplierRequest."""
        email = body.contact_info.primary_email.lower().strip()
        existing = await Supplier.find_one({"contact_info.primary_email": email})
        if existing:
            raise DuplicateError("Email already in use")

        ci = body.contact_info
        contact_info = SupplierContactInfo(
            primary_email=email,
            additional_emails=ci.additional_emails,
            primary_phone=ci.primary_phone,
            contact_person_name=ci.contact_person_name,
            contact_person_title=ci.contact_person_title,
            contact_person_email=ci.contact_person_email,
            contact_person_phone=ci.contact_person_phone,
        )

        addr = body.company_info.business_address
        business_address = CompanyAddress(
            street_address_1=addr.street_address_1,
            street_address_2=addr.street_address_2,
            city=addr.city,
            state=addr.state,
            zip_code=addr.zip_code,
            country=addr.country,
        )

        shipping_address = None
        if body.company_info.shipping_address:
            sa = body.company_info.shipping_address
            shipping_address = CompanyAddress(
                street_address_1=sa.street_address_1,
                street_address_2=sa.street_address_2,
                city=sa.city,
                state=sa.state,
                zip_code=sa.zip_code,
                country=sa.country,
            )

        company_info = CompanyInfo(
            legal_name=body.company_info.legal_name,
            dba_name=body.company_info.dba_name,
            business_address=business_address,
            shipping_address=shipping_address,
        )

        bi = body.business_info
        business_info = BusinessInfo(
            facebook_url=bi.facebook_url,
            instagram_handle=bi.instagram_handle,
            twitter_handle=bi.twitter_handle,
            linkedin_url=bi.linkedin_url,
            timezone=bi.timezone,
            support_email=bi.support_email,
            support_phone=bi.support_phone,
        )

        banking_info = None
        if body.banking_info:
            banking_info = BankingInfo(
                bank_name=body.banking_info.bank_name,
                account_holder_name=body.banking_info.account_holder_name,
                account_number_last4=body.banking_info.account_number_last4,
            )

        supplier = Supplier(
            password_hash=hash_password(body.password),
            contact_info=contact_info,
            company_info=company_info,
            business_info=business_info,
            banking_info=banking_info,
        )
        await supplier.insert()

        self._kafka.emit(
            event_type=EventType.SUPPLIER_CREATED,
            entity_id=oid_to_str(supplier.id),
            data=supplier.model_dump(mode="json"),
        )
        return supplier

    async def get_supplier(self, supplier_id: str) -> Supplier:
        try:
            supplier = await Supplier.get(PydanticObjectId(supplier_id))
        except Exception:
            raise NotFoundError("Supplier not found")
        if not supplier:
            raise NotFoundError("Supplier not found")
        return supplier

    async def list_suppliers(self, skip: int = 0, limit: int = 20) -> list[Supplier]:
        return (
            await Supplier.find_all()
            .skip(skip)
            .limit(min(limit, 100))
            .to_list()
        )

    async def update_supplier(
        self,
        supplier_id: str,
        primary_phone: Optional[str] = None,
        legal_name: Optional[str] = None,
        dba_name: Optional[str] = None,
        support_email: Optional[str] = None,
        support_phone: Optional[str] = None,
    ) -> Supplier:
        supplier = await self.get_supplier(supplier_id)

        if primary_phone is not None:
            supplier.contact_info.primary_phone = primary_phone
        if legal_name is not None:
            supplier.company_info.legal_name = legal_name
        if dba_name is not None:
            supplier.company_info.dba_name = dba_name
        if support_email is not None:
            supplier.business_info.support_email = support_email
        if support_phone is not None:
            supplier.business_info.support_phone = support_phone

        await supplier.save()

        self._kafka.emit(
            event_type=EventType.SUPPLIER_UPDATED,
            entity_id=oid_to_str(supplier.id),
            data=supplier.model_dump(mode="json"),
        )
        return supplier

    async def delete_supplier(self, supplier_id: str) -> None:
        supplier = await self.get_supplier(supplier_id)
        await supplier.delete()

        self._kafka.emit(
            event_type=EventType.SUPPLIER_DELETED,
            entity_id=oid_to_str(supplier.id),
            data={"supplier_id": oid_to_str(supplier.id)},
        )
