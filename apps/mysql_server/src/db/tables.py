"""CREATE TABLE definitions for the analytics database."""

TABLE_DEFINITIONS = [
    # ----------------------------------------------------------
    # users
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id         VARCHAR(24) PRIMARY KEY,
        email           VARCHAR(255) NOT NULL,
        phone           VARCHAR(50),
        display_name    VARCHAR(100) NOT NULL,
        avatar          TEXT,
        bio             VARCHAR(500),
        version         INT DEFAULT 1,
        deleted_at      DATETIME(6),
        created_at      DATETIME(6) NOT NULL,
        updated_at      DATETIME(6) NOT NULL,
        event_id        VARCHAR(36),
        event_timestamp DATETIME(6),
        INDEX idx_users_email (email),
        INDEX idx_users_created (created_at)
    )
    """,

    # ----------------------------------------------------------
    # suppliers
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id             VARCHAR(24) PRIMARY KEY,
        email                   VARCHAR(255) NOT NULL,
        primary_phone           VARCHAR(50) NOT NULL,
        contact_person_name     VARCHAR(200),
        contact_person_title    VARCHAR(200),
        contact_person_email    VARCHAR(255),
        contact_person_phone    VARCHAR(50),
        legal_name              VARCHAR(200) NOT NULL,
        dba_name                VARCHAR(200),
        street_address_1        VARCHAR(200),
        street_address_2        VARCHAR(200),
        city                    VARCHAR(100),
        state                   VARCHAR(100),
        zip_code                VARCHAR(20),
        country                 VARCHAR(2),
        support_email           VARCHAR(255),
        support_phone           VARCHAR(50),
        facebook_url            TEXT,
        instagram_handle        VARCHAR(100),
        twitter_handle          VARCHAR(100),
        linkedin_url            TEXT,
        timezone                VARCHAR(50),
        created_at              DATETIME(6) NOT NULL,
        updated_at              DATETIME(6) NOT NULL,
        event_id                VARCHAR(36),
        event_timestamp         DATETIME(6),
        INDEX idx_suppliers_email (email),
        INDEX idx_suppliers_legal_name (legal_name),
        INDEX idx_suppliers_country (country, state, city)
    )
    """,

    # ----------------------------------------------------------
    # products
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS products (
        product_id          VARCHAR(24) PRIMARY KEY,
        supplier_id         VARCHAR(24) NOT NULL,
        supplier_name       VARCHAR(200),
        name                VARCHAR(200) NOT NULL,
        short_description   VARCHAR(500),
        category            VARCHAR(50) NOT NULL,
        unit_type           VARCHAR(20) NOT NULL,
        base_sku            VARCHAR(100),
        brand               VARCHAR(100),
        base_price_cents    INT NOT NULL,
        status              VARCHAR(20) NOT NULL,
        view_count          INT DEFAULT 0,
        favorite_count      INT DEFAULT 0,
        purchase_count      INT DEFAULT 0,
        total_reviews       INT DEFAULT 0,
        published_at        DATETIME(6),
        created_at          DATETIME(6) NOT NULL,
        updated_at          DATETIME(6) NOT NULL,
        event_id            VARCHAR(36),
        event_timestamp     DATETIME(6),
        INDEX idx_products_supplier (supplier_id),
        INDEX idx_products_category (category),
        INDEX idx_products_status (status),
        INDEX idx_products_created (created_at)
    )
    """,

    # ----------------------------------------------------------
    # product_variants
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS product_variants (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        product_id      VARCHAR(24) NOT NULL,
        variant_key     VARCHAR(200) NOT NULL,
        variant_id      VARCHAR(100) NOT NULL,
        variant_name    VARCHAR(200) NOT NULL,
        attributes_json JSON,
        price_cents     INT NOT NULL,
        cost_cents      INT,
        quantity         INT DEFAULT 0,
        width_cm        DOUBLE,
        height_cm       DOUBLE,
        depth_cm        DOUBLE,
        image_url       TEXT,
        UNIQUE KEY uq_product_variant (product_id, variant_key),
        INDEX idx_variants_product (product_id),
        CONSTRAINT fk_variants_product FOREIGN KEY (product_id)
            REFERENCES products(product_id) ON DELETE CASCADE
    )
    """,

    # ----------------------------------------------------------
    # orders
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id                VARCHAR(24) PRIMARY KEY,
        order_number            VARCHAR(50) NOT NULL,
        customer_user_id        VARCHAR(24) NOT NULL,
        customer_display_name   VARCHAR(200),
        customer_email          VARCHAR(255),
        customer_phone          VARCHAR(50),
        shipping_recipient_name VARCHAR(200),
        shipping_phone          VARCHAR(50),
        shipping_street_1       VARCHAR(200),
        shipping_street_2       VARCHAR(200),
        shipping_city           VARCHAR(100),
        shipping_state          VARCHAR(100),
        shipping_zip_code       VARCHAR(20),
        shipping_country        VARCHAR(2),
        status                  VARCHAR(20) NOT NULL,
        created_at              DATETIME(6) NOT NULL,
        updated_at              DATETIME(6) NOT NULL,
        cancelled_reason        TEXT,
        event_id                VARCHAR(36),
        event_timestamp         DATETIME(6),
        UNIQUE KEY uq_order_number (order_number),
        INDEX idx_orders_customer (customer_user_id),
        INDEX idx_orders_status (status),
        INDEX idx_orders_created (created_at)
    )
    """,

    # ----------------------------------------------------------
    # order_items
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id                      INT AUTO_INCREMENT PRIMARY KEY,
        order_id                VARCHAR(24) NOT NULL,
        item_id                 VARCHAR(50) NOT NULL,
        product_id              VARCHAR(24) NOT NULL,
        supplier_id             VARCHAR(24) NOT NULL,
        product_name            VARCHAR(200),
        variant_name            VARCHAR(200),
        variant_attributes_json JSON,
        image_url               TEXT,
        supplier_name           VARCHAR(200),
        quantity                INT NOT NULL,
        unit_price_cents        INT NOT NULL,
        final_price_cents       INT NOT NULL,
        total_cents             INT NOT NULL,
        fulfillment_status      VARCHAR(20),
        shipped_quantity        INT DEFAULT 0,
        tracking_number         VARCHAR(100),
        carrier                 VARCHAR(100),
        shipped_at              DATETIME(6),
        delivered_at            DATETIME(6),
        UNIQUE KEY uq_order_item (order_id, item_id),
        INDEX idx_items_order (order_id),
        INDEX idx_items_product (product_id),
        CONSTRAINT fk_items_order FOREIGN KEY (order_id)
            REFERENCES orders(order_id) ON DELETE CASCADE
    )
    """,

    # ----------------------------------------------------------
    # posts
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS posts (
        post_id             VARCHAR(24) PRIMARY KEY,
        post_type           VARCHAR(20) NOT NULL,
        author_user_id      VARCHAR(24) NOT NULL,
        author_display_name VARCHAR(200),
        author_avatar       TEXT,
        author_type         VARCHAR(20),
        text_content        TEXT,
        media_json          JSON,
        link_url            TEXT,
        link_title          VARCHAR(200),
        link_description    VARCHAR(500),
        link_image          TEXT,
        link_site_name      VARCHAR(200),
        view_count          INT DEFAULT 0,
        like_count          INT DEFAULT 0,
        comment_count       INT DEFAULT 0,
        share_count         INT DEFAULT 0,
        save_count          INT DEFAULT 0,
        engagement_rate     DOUBLE DEFAULT 0.0,
        deleted_at          DATETIME(6),
        published_at        DATETIME(6),
        created_at          DATETIME(6) NOT NULL,
        updated_at          DATETIME(6) NOT NULL,
        event_id            VARCHAR(36),
        event_timestamp     DATETIME(6),
        INDEX idx_posts_author (author_user_id),
        INDEX idx_posts_type (post_type),
        INDEX idx_posts_published (published_at),
        INDEX idx_posts_created (created_at)
    )
    """,
]
