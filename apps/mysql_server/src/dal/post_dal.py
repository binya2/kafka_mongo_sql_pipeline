"""Data Access Layer for posts table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class PostDAL:

    def upsert_post(self, post_id, post_type,
                    author_user_id, author_display_name,
                    author_avatar, author_type,
                    text_content, media_json,
                    link_url, link_title, link_description,
                    link_image, link_site_name,
                    view_count, like_count, comment_count,
                    share_count, save_count, engagement_rate,
                    last_comment_at,
                    deleted_at, published_at, created_at, updated_at,
                    event_id, event_timestamp):
        """Insert or update a post in the posts table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            upsert_query = """
                           INSERT INTO posts (post_id, post_type, author_user_id, author_display_name,
                                              author_avatar, author_type, text_content, media_json,
                                              link_url, link_title, link_description, link_image,
                                              link_site_name, view_count, like_count, comment_count,
                                              share_count, save_count, engagement_rate, last_comment_at,
                                              deleted_at, published_at, created_at, updated_at,
                                              event_id, event_timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                   %s, %s, %s, %s, %s) ON DUPLICATE KEY
                           UPDATE
                               post_type=
                           VALUES (post_type), author_user_id=
                           VALUES (author_user_id), author_display_name=
                           VALUES (author_display_name), author_avatar=
                           VALUES (author_avatar), author_type=
                           VALUES (author_type), text_content=
                           VALUES (text_content), media_json=
                           VALUES (media_json), link_url=
                           VALUES (link_url), link_title=
                           VALUES (link_title), link_description=
                           VALUES (link_description), link_image=
                           VALUES (link_image), link_site_name=
                           VALUES (link_site_name), view_count=
                           VALUES (view_count), like_count=
                           VALUES (like_count), comment_count=
                           VALUES (comment_count), share_count=
                           VALUES (share_count), save_count=
                           VALUES (save_count), engagement_rate=
                           VALUES (engagement_rate), last_comment_at=
                           VALUES (last_comment_at), deleted_at=
                           VALUES (deleted_at), published_at=
                           VALUES (published_at), created_at=
                           VALUES (created_at), updated_at=
                           VALUES (updated_at), event_id=
                           VALUES (event_id), event_timestamp=
                           VALUES (event_timestamp)
                           """
            value = (
                post_id, post_type, author_user_id, author_display_name,
                author_avatar, author_type, text_content, media_json,
                link_url, link_title, link_description, link_image,
                link_site_name, view_count, like_count, comment_count,
                share_count, save_count, engagement_rate, last_comment_at,
                deleted_at, published_at, created_at, updated_at,
                event_id, event_timestamp
            )

            cursor.execute(upsert_query, value)
            connection.commit()
            logger.info(f"Upserted post with ID {post_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error upserting post with ID {post_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def soft_delete_post(self, post_id, event_id, event_timestamp):
        """Soft delete a post by setting deleted_at timestamp."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            delete_query = """
                           UPDATE posts
                           SET deleted_at      = NOW(3),
                               event_id        = %s,
                               event_timestamp = %s
                           WHERE post_id = %s
                           """
            value = (event_id, event_timestamp, post_id)
            cursor.execute(delete_query, value)
            connection.commit()
            logger.info(f"Soft deleted post with ID {post_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error soft deleting post with ID {post_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
