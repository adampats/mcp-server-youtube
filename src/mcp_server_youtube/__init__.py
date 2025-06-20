from .server import serve

def main():
    """MCP YouTube Server - Retrieve YouTube video transcripts and metadata"""
    import asyncio
    asyncio.run(serve())

if __name__ == "__main__":
    main()
