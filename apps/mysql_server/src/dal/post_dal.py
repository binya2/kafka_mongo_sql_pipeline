"""Data Access Layer for posts table."""

import json
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
                    deleted_at, published_at, created_at, updated_at,
                    event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posts
                    (post_id, post_type,
                     author_user_id, author_display_name,
                     author_avatar, author_type,
                     text_content, media_json,
                     link_url, link_title, link_description,
                     link_image, link_site_name,
                     view_count, like_count, comment_count,
                     share_count, save_count, engagement_rate,
                     deleted_at, published_at, created_at, updated_at,
                     event_id, event_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    post_type=VALUES(post_type),
                    author_display_name=VALUES(author_display_name),
                    author_avatar=VALUES(author_avatar),
                    text_content=VALUES(text_content),
                    media_json=VALUES(media_json),
                    link_url=VALUES(link_url), link_title=VALUES(link_title),
                    link_description=VALUES(link_description),
                    link_image=VALUES(link_image),
                    link_site_name=VALUES(link_site_name),
                    view_count=VALUES(view_count),
                    like_count=VALUES(like_count),
                    comment_count=VALUES(comment_count),
                    share_count=VALUES(share_count),
                    save_count=VALUES(save_count),
                    engagement_rate=VALUES(engagement_rate),
                    deleted_at=VALUES(deleted_at),
                    published_at=VALUES(published_at),
                    updated_at=VALUES(updated_at),
                    event_id=VALUES(event_id),
                    event_timestamp=VALUES(event_timestamp)
            """, (post_id, post_type,
                  author_user_id, author_display_name,
                  author_avatar, author_type,
                  text_content, media_json,
                  link_url, link_title, link_description,
                  link_image, link_site_name,
                  view_count, like_count, comment_count,
                  share_count, save_count, engagement_rate,
                  deleted_at, published_at, created_at, updated_at,
                  event_id, event_timestamp))
            cursor.close()
        finally:
            conn.close()

    def soft_delete_post(self, post_id, event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE posts SET deleted_at = NOW(6),
                    event_id = %s, event_timestamp = %s
                WHERE post_id = %s
            """, (event_id, event_timestamp, post_id))
            cursor.close()
        finally:
            conn.close()
