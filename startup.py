"""
Combined startup script for running the web server
with an integrated worker process on Render's free tier.
"""
import os
import sys
import uvicorn
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("startup")

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Run the webhook service")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), 
                        help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", 
                        help="Host to run the server on")
    parser.add_argument("--workers", type=int, default=1, 
                        help="Number of worker processes (use 1 for free tier)")
    
    args = parser.parse_args()
    
    logger.info(f"Starting webhook service on {args.host}:{args.port}")
    logger.info(f"Using {'internal worker thread' if args.workers == 1 else f'{args.workers} workers'}")
    
    # Start Uvicorn with the app
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info"
    )

if __name__ == "__main__":
    main()