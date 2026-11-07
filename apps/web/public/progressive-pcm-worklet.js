class OryntelaPcmTap extends AudioWorkletProcessor {
  constructor() {
    super();
    this.nextSequence = 0;
    this.pendingDrainToken = null;
    this.drained = false;
    this.port.onmessage = (event) => {
      const message = event.data;
      if (
        message?.type === "drain" &&
        typeof message.token === "string" &&
        !this.drained &&
        this.pendingDrainToken === null
      ) {
        this.pendingDrainToken = message.token;
      }
    };
  }

  process(inputs) {
    if (this.drained) return true;
    const channels = inputs[0];
    if (channels && channels.length > 0 && channels[0].length > 0) {
      const mono = new Float32Array(channels[0].length);
      for (
        let channelIndex = 0;
        channelIndex < channels.length;
        channelIndex += 1
      ) {
        const channel = channels[channelIndex];
        for (let index = 0; index < mono.length; index += 1) {
          mono[index] += channel[index] / channels.length;
        }
      }
      this.port.postMessage(
        { type: "pcm", sequence: this.nextSequence, samples: mono },
        [mono.buffer],
      );
      this.nextSequence += 1;
    }
    if (this.pendingDrainToken !== null) {
      const token = this.pendingDrainToken;
      this.pendingDrainToken = null;
      this.drained = true;
      this.port.postMessage({
        type: "drain_ack",
        token,
        finalSequence: this.nextSequence - 1,
      });
    }
    return true;
  }
}

registerProcessor("oryntela-pcm-tap", OryntelaPcmTap);
