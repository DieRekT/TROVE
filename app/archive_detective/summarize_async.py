import asyncio, logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Global summary queue
summary_queue = asyncio.Queue()

# Status tracking for research jobs
research_status: dict[str, dict] = {}

async def summarize_text(text: str) -> dict:
    """Minimal async summariser using OpenAI Chat API."""
    try:
        from openai import AsyncOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, skipping summarization")
            return {"summary": "", "bullets": []}
        
        client = AsyncOpenAI(api_key=api_key)
        prompt = f"Summarise this Trove article in 3–5 bullet points:\n\n{text[:8000]}"
        
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        content = resp.choices[0].message.content.strip()
        bullets = [b.strip("-• ") for b in content.splitlines() if b.strip()]
        return {"summary": "\n".join(bullets), "bullets": bullets}
    except Exception as e:
        logger.warning(f"Summarization error: {e}")
        return {"summary": "", "bullets": []}

async def queue_summary(sid: str, article_id: str, text: str, job_id: Optional[str] = None):
    """Queue an article for summarization."""
    await summary_queue.put((sid, article_id, text, job_id))

async def summary_worker():
    """Background worker that processes summarization queue."""
    logger.info("Summary worker started")
    while True:
        try:
            sid, article_id, text, job_id = await summary_queue.get()
            
            # Update status if job_id provided
            if job_id and job_id in research_status:
                research_status[job_id]["processed"] = research_status[job_id].get("processed", 0) + 1
                research_status[job_id]["status"] = "processing"
            
            try:
                result = await summarize_text(text)
                
                # Try to update article summary in context store
                try:
                    from app.context_store import update_article_summary
                    update_article_summary(sid, article_id, result["summary"], result["bullets"])
                except ImportError:
                    logger.warning("update_article_summary not available")
                except Exception as e:
                    logger.warning(f"Failed to update article summary: {e}")
                
                # Try to store embedding if available
                try:
                    from app.embeddings import generate_embedding
                    from app.context_store import store_embedding
                    emb = await generate_embedding(text)
                    store_embedding(sid, article_id, emb)
                except ImportError:
                    logger.debug("Embeddings not available, skipping")
                except Exception as e:
                    logger.debug(f"Embedding storage failed: {e}")
                
                logger.info(f"✓ summarised + embedded {article_id}")
                
                # Update status
                if job_id and job_id in research_status:
                    research_status[job_id]["summarized"] = research_status[job_id].get("summarized", 0) + 1
                    
            except Exception as e:
                logger.warning(f"Summary worker error {article_id}: {e}")
            finally:
                summary_queue.task_done()
                
        except Exception as e:
            logger.error(f"Summary worker queue error: {e}")
            await asyncio.sleep(1)

