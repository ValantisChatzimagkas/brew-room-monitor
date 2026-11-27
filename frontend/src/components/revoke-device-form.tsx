"use client";

import { useActionState, useState } from "react";

import { revokeDevice } from "@/app/devices/[id]/settings/actions";
import { Button } from "@/components/ui/button";

/** "Revoke" button that opens an inline confirmation; nothing is sent until it is confirmed. */
export function RevokeDeviceForm({ deviceId, deviceName }: { deviceId: number; deviceName: string }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Revoke
      </Button>
    );
  }
  return <OpenForm deviceId={deviceId} deviceName={deviceName} onClose={() => setOpen(false)} />;
}

function OpenForm({ deviceId, deviceName, onClose }: { deviceId: number; deviceName: string; onClose: () => void }) {
  const [, formAction, pending] = useActionState(revokeDevice.bind(null, deviceId), null);
  return (
    <form action={formAction} className="flex max-w-md flex-col gap-3">
      <p className="text-sm">
        {deviceName} stops sending readings until you re-key it and flash the new token. Its readings stay.
      </p>
      <div className="flex gap-2">
        <Button type="submit" variant="destructive" disabled={pending}>
          Revoke device
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Keep it
        </Button>
      </div>
    </form>
  );
}
