# Proof of interruption handler (Step 3)

This submission demonstrates:

Agent ignores filler ("yeah") while speaking  
Agent responds to "yeah" when silent  
Agent stops on hard interrupt ("stop")

## Case 1: Agent ignores "yeah" while speaking

[AGENT] Speaking: "Sure, let me explain the steps..."
[USER] yeah
[INTERRUPT_HANDLER] normalized="yeah"
[INTERRUPT_HANDLER] filler_only=True
[ACTION] Ignored interruption (agent continues speaking)

## Case 2: Agent responds to "yeah" when silent

[AGENT] (silent / listening)
[USER] yeah
[INTERRUPT_HANDLER] normalized="yeah"
[INTERRUPT_HANDLER] filler_only=True
[ACTION] Treated as user input, agent responds.

---

## Case 3: Agent stops for "stop"

[AGENT] Speaking: "Now I will continue with the next explanation..."
[USER] stop
[INTERRUPT_HANDLER] normalized="stop"
[INTERRUPT_HANDLER] hard_interrupt=True
[ACTION] Speech interrupted / stopped immediately.
