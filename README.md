# Agents on the critical path: Cal Poly TPM talk

**Slides:** https://discofuchsia.github.io/cal-poly-ai-project-management-agent-and-mcp/  
**Live demo:** https://discofuchsia.github.io/cal-poly-ai-project-management-agent-and-mcp/#10

- `index.html`: the deck (17 slides). Open it in Chrome and press F for fullscreen. Arrow keys move between slides. It needs no internet.
- Slide 10 is the in-browser demo: click a prompt chip, approve or deny the writes, and press "reset board" between run-throughs.
- `demo/`: the real MCP server and agent.

## Demo run of show (about 6 minutes)

1. Slide 10, "What's at risk this sprint?" The answer is RED: the critical path runs into blocked R-104, and R-109 has no owner.
2. "Fix ownership gaps and rebalance." Approve both writes and watch the cards and load bars move. Point out that Maya is still overloaded, because a scope call stays with the human.
3. "The encoder arrived. Unblock R-104." Approve it. The risk count drops.
4. "Draft Friday's leadership update." Every number comes from one tool call.
5. Optional: switch to the terminal for the real thing:

```bash
cd demo
python3 pm_board_server.py --reset   # fresh board with dates relative to today
python3 wire_demo.py                 # raw JSON-RPC between host and server
kiro-cli chat --agent pm-agent       # real LLM agent over MCP (run `kiro-cli login` first)
```

The server uses only the Python standard library and talks over stdio. It opens no network port.
