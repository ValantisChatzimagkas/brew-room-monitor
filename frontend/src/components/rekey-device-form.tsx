"use client";

import { useActionState, useState } from "react";

import { rekeyDevice } from "@/app/devices/[id]/actions";
import { DeviceToken, FIRMWARE_DOCS, useResetOnHide } from "@/components/device-token";
import { Button, buttonVariants } from "@/components/ui/button";

/**
 * "Re-key" button that opens an inline confirmation, then shows the new token once. The token lives only in
 * the inner form's action state, so re-keying the inner form drops it.
 */
export function RekeyDeviceForm({ deviceId, deviceName }: { deviceId: number; deviceName: string }) {
  const [key, reset] = useResetOnHide();
  return <Inner key={key} deviceId={deviceId} deviceName={deviceName} onDone={reset} />;
}

function Inner({ deviceId, deviceName, onDone }: { deviceId: number; deviceName: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [state, formAction, pending] = useActionState(rekeyDevice.bind(null, deviceId), { token: null });

  if (state.token !== null) {
    return (
      <div className="flex w-full max-w-xl flex-col gap-4">
        <DeviceToken token={state.token} />
        <div className="flex flex-wrap gap-2">
          <a
            href={FIRMWARE_DOCS}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            How to flash it
          </a>
          <Button onClick={onDone}>Done</Button>
        </div>
      </div>
    );
  }

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Re-key
      </Button>
    );
  }

  return (
    <form action={formAction} className="flex max-w-md flex-col gap-3">
      <p className="text-sm">
        {deviceName}&apos;s current token stops working now. It can&apos;t send readings until you flash the new
        token.
      </p>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          Re-key device
        </Button>
        <Button type="button" variant="outline" onClick={() => setOpen(false)}>
          Keep it
        </Button>
      </div>
    </form>
  );
}
