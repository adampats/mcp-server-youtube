from typing import Annotated, Dict, Any
import re
from urllib.parse import urlparse, parse_qs
import signal
import sys
import textwrap

from mcp.shared.exceptions import McpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ErrorData,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel, Field, AnyUrl
import yt_dlp


def clean_transcript_text(text: str) -> str:
    """
    Clean up transcript text by removing VTT formatting, HTML tags, and inline timestamps
    Args:
        text (str): Raw transcript text
    Returns:
        str: Cleaned transcript text with formatting removed and whitespace normalized
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if (not line or 
            line.startswith('WEBVTT') or 
            line.startswith('Kind:') or
            line.startswith('Language:') or
            '-->' in line or
            line.isdigit() or
            re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}', line)):
            continue
        cleaned_lines.append(line)
    
    cleaned_text = ' '.join(cleaned_lines)
    
    # remove inline timestamps like <00:00:00.320>
    cleaned_text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', cleaned_text)
    
    # remove HTML tags like <c> or </c>
    cleaned_text = re.sub(r'<[^>]*>', '', cleaned_text)
    
    # replace multiple spaces with single space
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    return cleaned_text.strip()


async def get_youtube_transcript_and_metadata(
    url: str, raw: bool = False
) -> Dict[str, Any]:
    """
    Fetch YouTube video transcript and metadata using yt-dlp
    Args:
        url (str): The YouTube video URL to fetch transcript and metadata from
        raw (bool, optional): If True, returns the raw transcript without cleaning. 
    Returns:
        A dictionary containing transcript, metadata, and length
    """

    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            metadata = {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown Uploader'),
                'upload_date': info.get('upload_date', 'Unknown Date'),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'description': info.get('description', ''),
            }
            
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            transcript_text = ""
            preferred_languages = ['en', 'en-US', 'en-GB']
            
            # First try manual subtitles
            for lang in preferred_languages:
                if lang in subtitles:
                    subtitle_info = subtitles[lang]
                    if subtitle_info:
                        # prefer vtt
                        for sub in subtitle_info:
                            if sub.get('ext') == 'vtt':
                                transcript_text = ydl.urlopen(sub['url']).read().decode('utf-8')
                                break
                        if transcript_text:
                            break
            
            # If no manual subtitles, try automatic captions
            if not transcript_text:
                for lang in preferred_languages:
                    if lang in automatic_captions:
                        caption_info = automatic_captions[lang]
                        if caption_info:
                            for sub in caption_info:
                                if sub.get('ext') == 'vtt':
                                    transcript_text = ydl.urlopen(sub['url']).read().decode('utf-8')
                                    break
                            if transcript_text:
                                break
            
            if not transcript_text:
                raise McpError(ErrorData(
                    code=INTERNAL_ERROR, 
                    message="No transcript/subtitles available for this video"
                ))
            
            cleaned_transcript = transcript_text if raw else clean_transcript_text(transcript_text)
            
            return {
                'transcript': cleaned_transcript,
                'metadata': metadata,
                'original_length': len(cleaned_transcript),
            }
            
    except Exception as e:
        if isinstance(e, McpError):
            raise
        raise McpError(ErrorData(
            code=INTERNAL_ERROR, 
            message=f"Failed to fetch YouTube transcript: {str(e)}"
        ))


class Youtube(BaseModel):
    """Parameters for fetching a YouTube video transcript and metadata."""

    url: Annotated[AnyUrl, Field(description="YouTube video URL to fetch transcript from")]
    raw: Annotated[
        bool,
        Field(
            default=False,
            description="Get the raw VTT transcript content without cleaning up timestamps and formatting.",
        ),
    ]


async def serve() -> None:
    """Run the YouTube transcript MCP server."""
    server = Server("mcp-server-youtube")

    def signal_handler(signum, frame):
        print("Received signal to terminate", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="get_youtube",
                description=textwrap.dedent("""
                    Fetches a YouTube video transcript and metadata.
                    This tool can retrieve full transcripts (subtitles) from YouTube videos along with metadata
                    like title, uploader, and upload date. It automatically cleans up VTT formatting to reduce
                    token usage unless raw format is requested. Returns the complete transcript without truncation.
                """).strip(),
                inputSchema=Youtube.model_json_schema(),
            )
        ]

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="get_youtube",
                description="Fetch a YouTube video transcript and metadata",
                arguments=[
                    PromptArgument(
                        name="url", description="YouTube video URL to fetch", required=True
                    )
                ],
            )
        ]

    @server.call_tool()
    async def call_tool(name, arguments: dict) -> list[TextContent]:
        if name != "get_youtube":
            raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Unknown tool: {name}"))
            
        try:
            args = Youtube(**arguments)
        except ValueError as e:
            raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))

        url = str(args.url)
        if not url:
            raise McpError(ErrorData(code=INVALID_PARAMS, message="URL is required"))

        result = await get_youtube_transcript_and_metadata(
            url, raw=args.raw
        )
        
        # Format the response
        metadata = result['metadata']
        transcript = result['transcript']
        formatted_response = textwrap.dedent(f"""
            **Video Information:**
            - Title: {metadata['title']}
            - Uploader: {metadata['uploader']}
            - Upload Date: {metadata['upload_date']}
            - Duration: {metadata['duration']} seconds
            - View Count: {metadata.get('view_count', 'N/A')}

            **Transcript:**
            {transcript}
        """).strip()
        
        return [TextContent(type="text", text=formatted_response)]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        if name != "get_youtube":
            raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Unknown prompt: {name}"))
            
        if not arguments or "url" not in arguments:
            raise McpError(ErrorData(code=INVALID_PARAMS, message="URL is required"))

        url = arguments["url"]

        try:
            result = await get_youtube_transcript_and_metadata(url)
            metadata = result['metadata']
            transcript = result['transcript']
            
            formatted_content = textwrap.dedent(f"""
                Video: {metadata['title']}
                Uploader: {metadata['uploader']}
                Upload Date: {metadata['upload_date']}

                Transcript:
                {transcript}
            """).strip()
            
            return GetPromptResult(
                description=f"YouTube transcript for: {metadata['title']}",
                messages=[
                    PromptMessage(
                        role="user", 
                        content=TextContent(type="text", text=formatted_content)
                    )
                ],
            )
        except McpError as e:
            return GetPromptResult(
                description=f"Failed to fetch YouTube transcript",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=str(e)),
                    )
                ],
            )

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
