# YouTube Transcript MCP Server

A Model Context Protocol server that fetches Youtube video transcripts and metadata. This server enables LLMs to retrieve transcripts for purposes of summarizing and asking questions about video content. It automatically cleans up the VTT format to reduce token usage by removing timestamps and formatting, unless raw format is requested.

It leverages the [yt-dlp](https://github.com/yt-dlp/yt-dlp) library for the heavy lifting with Youtube fetching, as it seems to be the most reliable.

### Features

- Extracts video transcripts using yt-dlp
- Retrieves video metadata (title, uploader, upload date, duration, view count)
- Supports both manual subtitles and automatic captions
- Automatically cleans VTT formatting to reduce token usage
- Returns complete transcripts without truncation
- Supports multiple YouTube URL formats

### Available Tools

- `get_youtube` - Fetches a complete transcript and metadata from a YouTube video
    - `url` (string, required): YouTube video URL to fetch transcript from
    - `raw` (boolean, optional): Get raw VTT content without cleanup (default: false)

### Prompts

- **get_youtube**
  - Fetch a YouTube video transcript and metadata
  - Arguments:
    - `url` (string, required): YouTube video URL to fetch

### Run it

```bash
# <Clone this repo>
cd mcp-server-youtube
uv sync
uv run mcp-server-youtube
```

Using [Inspector](https://github.com/modelcontextprotocol/inspector) for testing:

```bash
npx @modelcontextprotocol/inspector uv run mcp-server-youtube
```

### Server config file (using Docker)

Build the image:

```bash
docker build -t mcp-server-youtube .
```

Add to claude_desktop_config.json:

```json
{
  "mcpServers": {
    "youtube": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "mcp-server-youtube"],
      "cwd": "/path/to/code/repos/mcp-server-youtube"
    }
  }
}
```
