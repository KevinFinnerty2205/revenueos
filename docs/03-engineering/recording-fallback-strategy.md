# Recording fallback strategy

Recording is optional. Failure or refusal must preserve a useful Interaction.

| Condition                    | Product response                                                      | Data created                              |
| ---------------------------- | --------------------------------------------------------------------- | ----------------------------------------- |
| Consent declined             | Continue in passive Companion                                         | No recording session                      |
| Unsupported browser/MIME     | Explain limitation and offer passive mode                             | No recording session                      |
| Microphone permission denied | Explain denial and offer debrief/visual capture                       | No audio                                  |
| Phone call                   | Force passive mode; do not imply call audio capture                   | No recording session                      |
| Online meeting               | Force passive mode; do not imply system-audio capture                 | No recording session                      |
| Temporary connection loss    | Retain bounded chunks in the current tab and retry                    | Server sees only received/verified chunks |
| Reload after verified chunks | Show interrupted state and finalisation/cancel options                | Verified server chunks remain             |
| Reload before chunk upload   | Explain that unsent browser-memory audio is unavailable               | No fabricated recovery                    |
| Recording failure            | Preserve verified chunks; allow retry/cancel; keep Interaction usable | Safe failure metadata only                |

Passive capture continues to offer markers and authorised photos. AFTER always
offers the existing AI Debrief, typed fallback and Voice Journal safety flow when
enabled. No fallback silently starts another capture channel.
