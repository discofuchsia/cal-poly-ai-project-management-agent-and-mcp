# Agents on the critical path: Cal Poly TPM talk

**Slides:** https://discofuchsia.github.io/cal-poly-ai-project-management-agent-and-mcp/  
**Live demo:** https://discofuchsia.github.io/cal-poly-ai-project-management-agent-and-mcp/#10

- `index.html`: the deck (17 slides). Open it in Chrome and press F for fullscreen. Arrow keys move between slides. It needs no internet.
- Slide 10 is the in-browser demo: click a prompt chip, approve or deny the writes, and press "reset board" between run-throughs.
- `demo/`: the real MCP server and agent.

## Demo run of show (about 6 minutes)

1. Slide 10, "Pull · what's at risk?" The answer is RED: the critical path runs into blocked R-104, and R-109 has no owner.
2. "Push · fix ownership gaps." Approve both writes and watch the cards and load bars move. Point out that Maya is still overloaded, because a scope call stays with the human.
3. "Push · unblock R-104." Approve it. The risk count drops.
4. "Pull · draft leadership update." Every number comes from one tool call.
5. "Push · publish to Harbor." The agent uses a second MCP server (a docs portal) to publish the update, after approval. In the public copy the Harbor calls are simulated.
6. Optional: switch to the terminal for the real thing:

```bash
cd demo
python3 pm_board_server.py --reset   # fresh board with dates relative to today
python3 wire_demo.py                 # raw JSON-RPC between host and server
kiro-cli chat --agent pm-agent       # real LLM agent over MCP (run `kiro-cli login` first)
```

To publish for real from the terminal, add your docs-portal MCP server to the agent's `mcpServers` alongside the board.

The server uses only the Python standard library and talks over stdio. It opens no network port.
