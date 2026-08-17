import { spawnSync } from "node:child_process"

function runHook(event, payload) {
  const result = spawnSync("hc", ["hook", "opencode", event], {
    input: JSON.stringify(payload),
    encoding: "utf8",
  })
  if (result.status !== 0) {
    return null
  }
  const text = (result.stdout || "").trim()
  if (!text) {
    return null
  }
  return JSON.parse(text)
}

export const HybridCoco = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const decision = runHook("pre-tool-use", {
        tool_name: input.tool,
        tool_input: output.args,
      })
      if (decision && decision.block === true) {
        throw new Error(decision.reason)
      }
    },
    "tool.execute.after": async (input) => {
      spawnSync("hc", ["hook", "opencode", "post-tool-use"], {
        input: JSON.stringify({
          tool_name: input.tool,
          tool_input: {},
        }),
        encoding: "utf8",
      })
    },
  }
}
