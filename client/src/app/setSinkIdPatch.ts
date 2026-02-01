/**
 * Browser requires a user gesture to call setSinkId(). Pipecat may call it on
 * speaker update (after connect), outside a gesture. Patch to no-op on
 * NotAllowedError so audio falls back to default device.
 */
if (typeof window !== 'undefined' && typeof HTMLMediaElement !== 'undefined') {
  const proto = HTMLMediaElement.prototype;
  if (proto.setSinkId) {
    const native = proto.setSinkId;
    proto.setSinkId = function (this: HTMLMediaElement, sinkId: string) {
      return native.call(this, sinkId).catch((err: unknown) => {
        if (err instanceof Error && err.name === 'NotAllowedError') return;
        throw err;
      });
    };
  }
}
