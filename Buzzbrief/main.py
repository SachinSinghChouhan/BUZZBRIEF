from fastapi import FastAPI, Query
from dotenv import load_dotenv
import os
import ssl
import asyncpg
import logging
from typing import Optional
from azure_audio_service import generate_audio_from_text  # <-- Add this import

#load environment variables from .env file
load_dotenv()

# Get the database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL","postgresql://postgres.bzvinlggnrivnycbfkjv:jaishreeram@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")

#create an SSL context for secure connection since Supabase requires SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Add TTS configuration
TTS_API_KEY = os.getenv("TTS_API_KEY")
TTS_API_URL = os.getenv("TTS_API_URL", "https://api.elevenlabs.io/v1/text-to-speech")

async def connect_to_db():
    """Establish a connection to the database using asyncpg"""
    try:
        if not DATABASE_URL:
            raise ValueError("Database URL not configured")
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            ssl=ssl_context,
            command_timeout=20,  # reduced from 30
            min_size=1,
            max_size=2,  # reduced from 5
            timeout=10,
            max_inactive_connection_lifetime=10,  # Keep alive Supabase's limits
        )
        # Test connection
        async with pool.acquire() as conn:
            await conn.fetchval('SELECT 1')
        
        logging.info("Database connection established successfully")  
        return pool  
        
    except (asyncpg.PostgresError, ValueError, AttributeError) as e:
        raise ConnectionError(f"Failed to connect to database: {str(e)}")
    
app=FastAPI()

#Route to fetch news articles by date
@app.get("/{month}/{date}/{year}")
async def get_news_by_date(month:int, date:int, year:int):
    """Fetch the latest 20 news articles from the database for a specific date"""
    try:
        # Connect to the database
        pool = await connect_to_db()
        
        # Fetch latest 20 news articles for the specified date
        async with pool.acquire() as conn:
            query = """
                SELECT * FROM articles 
                WHERE EXTRACT(MONTH FROM published_at) = $1 
                AND EXTRACT(DAY FROM published_at) = $2 
                AND EXTRACT(YEAR FROM published_at) = $3
                ORDER BY published_at DESC
                LIMIT 20
            """
            articles = await conn.fetch(query, month, date, year)
        
        return {"articles": articles}
    
    except Exception as e:
        logging.error(f"Error fetching articles: {str(e)}")
        return {"error": str(e)}
    finally:
        # Close the connection pool
        if pool:
            await pool.close()
            logging.info("Database connection pool closed")


#Route to fetch news articles by category
@app.get("/category/{category}")
async def get_news_by_category(category:str):
    """Fetch news articles from the database for a specific category"""
    try:
        # Connect to the database
        pool = await connect_to_db()
        
        # Fetch news articles for the specified category
        async with pool.acquire() as conn:
            query = """
                SELECT * FROM articles 
                WHERE category = $1
            """
            articles = await conn.fetch(query, category)
        
        return {"articles": articles}
    
    except Exception as e:
        logging.error(f"Error fetching articles: {str(e)}")
        return {"error": str(e)}
    finally:
        # Close the connection pool
        if pool:
            await pool.close()
            logging.info("Database connection pool closed")


#Route to show complete article
@app.get("/article/{id}")
async def get_article_by_id(id: int):
    """Fetch a specific article from the database by its ID"""
    try:
        # Connect to the database
        pool = await connect_to_db()
        
        # Fetch the article for the specified ID
        async with pool.acquire() as conn:
            query = "SELECT id, title, content, url, category, source, created_at FROM articles WHERE id = $1"
            article = await conn.fetchrow(query, id)
            if not article:
                return {"error": "Article not found"}
            return dict(article)
    
    except Exception as e:
        logging.error(f"Error fetching article: {str(e)}")
        return {"error": str(e)}
    finally:
        # Close the connection pool
        if pool:
            await pool.close()
            logging.info("Database connection pool closed")

#Route to fetch article summary and generate TTS audio URL
@app.get("/article/{id}/summary")
async def get_article_summary(id: int, include_audio: Optional[bool] = Query(False, description="Whether to include TTS audio URL")):
    """Fetch article summary and optionally generate TTS audio URL"""
    try:
        pool = await connect_to_db()
        
        async with pool.acquire() as conn:
            # First get the article summary
            summary_query = """
                SELECT s.summary, a.id as article_id 
                FROM summaries s
                JOIN articles a ON s.article_id = a.id
                WHERE a.id = $1
            """
            summary_result = await conn.fetchrow(summary_query, id)
            
            if not summary_result:
                # If summary not found, generate it
                article_query = "SELECT content FROM articles WHERE id = $1"
                article_row = await conn.fetchrow(article_query, id)
                if not article_row:
                    return {"error": "Article not found"}
                article_content = article_row['content']
                # Placeholder summary generation logic
                generated_summary = article_content[:300] + "..." if article_content else "No content to summarize."
                # Store the generated summary
                insert_summary_query = """
                    INSERT INTO summaries (article_id, summary)
                    VALUES ($1, $2)
                    ON CONFLICT (article_id) DO UPDATE SET summary = EXCLUDED.summary
                """
                await conn.execute(insert_summary_query, id, generated_summary)
                summary = generated_summary
                article_id = id
            else:
                summary = summary_result['summary']
                article_id = summary_result['article_id']
            
            response_data = {"summary": summary}
            
            # If audio is requested, generate and store the audio URL
            if include_audio:
                # Check if we already have an audio URL for this article
                audio_query = """
                    SELECT audio_url FROM audio_requests 
                    WHERE article_id = $1 
                    ORDER BY requested_at DESC 
                    LIMIT 1
                """
                existing_audio = await conn.fetchval(audio_query, article_id)
                
                if existing_audio:
                    response_data["audio_url"] = existing_audio
                else:
                    # Generate new audio URL using Azure TTS service
                    try:
                        audio_url = generate_audio_from_text(summary)
                        # Store the audio request in the database
                        insert_query = """
                            INSERT INTO audio_requests (article_id, type, audio_url, requested_at)
                            VALUES ($1, 'summary', $2, NOW())
                        """
                        await conn.execute(insert_query, article_id, audio_url)
                        response_data["audio_url"] = audio_url
                    except Exception as tts_exc:
                        logging.error(f"Azure TTS error: {str(tts_exc)}")
                        response_data["error"] = "Failed to generate audio"
            
            return response_data
            
    except Exception as e:
        logging.error(f"Error fetching summary: {str(e)}")
        return {"error": str(e)}
    finally:
        if pool:
            await pool.close()
            logging.info("Database connection pool closed")

#Route to fetch more articles for homepage with pagination
@app.get("/articles")
async def get_articles(offset: int = Query(0, ge=0), limit: int = Query(10, gt=0, le=50)):
    """
    Fetch paginated articles for homepage with has_more indicator.
    """
    try:
        pool = await connect_to_db()
        async with pool.acquire() as conn:
            # Fetch articles with pagination
            articles_query = """
                SELECT id, title, content, url, category, source, created_at
                FROM articles
                ORDER BY published_at DESC
                OFFSET $1 LIMIT $2
            """
            articles = await conn.fetch(articles_query, offset, limit)
            # Check if there are more articles
            count_query = "SELECT COUNT(*) FROM articles"
            total_count = await conn.fetchval(count_query)
            has_more = (offset + limit) < total_count
            return {
                "articles": [dict(a) for a in articles],
                "has_more": has_more
            }
    except Exception as e:
        logging.error(f"Error fetching paginated articles: {str(e)}")
        return {"error": str(e)}
    finally:
        if pool:
            await pool.close()
            logging.info("Database connection pool closed")

