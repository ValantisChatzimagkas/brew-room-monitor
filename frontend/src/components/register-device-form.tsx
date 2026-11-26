"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { type FormEvent, startTransition, useActionState, useLayoutEffect, useState } from "react";
import { flushSync } from "react-dom";

import { registerDevice } from "@/app/devices/new/actions";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

type Room = { id: number; name: string };

const FIRMWARE_DOCS =
  "https://github.com/ValantisChatzimagkas/brew-room-monitor/blob/main/firmware/README.md#2-send-readings";

const next = (key: number) => key + 1;

/**
 * Form that registers a device and then shows its token once. The token lives only in the inner form's
 * action state, so re-keying the inner form drops it.
 */
export function RegisterDeviceForm({ rooms }: { rooms: Room[] }) {
  const [formKey, setFormKey] = useState(0);
  // The token must never come back: Next keeps a hidden route mounted in <Activity> (this cleanup runs on
  // hide), and the browser's back/forward cache keeps the whole page (pagehide, flushed so the snapshot
  // holds no token). Empty deps: a `refresh()` that changes `rooms` must not clear the token on screen.
  useLayoutEffect(() => {
    const onPageHide = () => flushSync(() => setFormKey(next));
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      setFormKey(next);
    };
  }, []);
  return <OpenForm key={formKey} rooms={rooms} onReset={() => setFormKey(next)} />;
}

function OpenForm({ rooms, onReset }: { rooms: Room[]; onReset: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("ambient");
  const [room, setRoom] = useState(rooms[0] ? String(rooms[0].id) : "");
  const [state, formAction, pending] = useActionState(registerDevice, { errors: {}, created: null });
  const { errors, created } = state;

  if (created) {
    return (
      <div className="flex max-w-xl flex-col gap-4">
        <p>
          <span className="font-medium">{created.name}</span> is registered.
        </p>
        <DeviceToken token={created.token} />
        <div className="flex flex-wrap gap-2">
          <Link href={`/devices/${created.id}`} className={buttonVariants({ variant: "outline" })}>
            Open {created.name}
          </Link>
          <Link href="/" className={buttonVariants({ variant: "outline" })}>
            Dashboard
          </Link>
          <a
            href={FIRMWARE_DOCS}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            How to flash it
          </a>
          <Button onClick={onReset}>Register another</Button>
        </div>
      </div>
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => formAction({ name, kind, room, newRoom: "" }));
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-sm flex-col gap-4">
      <Field data-invalid={errors.name !== undefined || undefined}>
        <FieldLabel htmlFor="device-name">Name</FieldLabel>
        <Input
          id="device-name"
          value={name}
          maxLength={64}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={errors.name !== undefined || undefined}
        />
        <FieldError>{errors.name}</FieldError>
      </Field>
      <Field data-invalid={errors.kind !== undefined || undefined}>
        <FieldLabel htmlFor="device-kind">Kind</FieldLabel>
        <NativeSelect
          id="device-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          aria-invalid={errors.kind !== undefined || undefined}
        >
          <NativeSelectOption value="ambient">Ambient (measures a room)</NativeSelectOption>
          <NativeSelectOption value="in_vessel">In vessel (floats in the fermenter)</NativeSelectOption>
        </NativeSelect>
        <FieldError>{errors.kind}</FieldError>
      </Field>
      {kind === "ambient" && (
        <Field data-invalid={errors.room !== undefined || undefined}>
          <FieldLabel htmlFor="device-room">Room</FieldLabel>
          <NativeSelect
            id="device-room"
            value={room}
            onChange={(e) => setRoom(e.target.value)}
            aria-invalid={errors.room !== undefined || undefined}
          >
            {rooms.length === 0 && <NativeSelectOption value="">No rooms yet</NativeSelectOption>}
            {rooms.map((r) => (
              <NativeSelectOption key={r.id} value={String(r.id)}>
                {r.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldError>{errors.room}</FieldError>
        </Field>
      )}
      <FieldError>{errors.form}</FieldError>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          Register device
        </Button>
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          Cancel
        </Link>
      </div>
    </form>
  );
}

function DeviceToken({ token }: { token: string }) {
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");

  async function copyToken() {
    try {
      // `navigator.clipboard` is undefined outside a secure context (plain HTTP on the LAN): that throws here too.
      await navigator.clipboard.writeText(token);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  }

  return (
    <Field>
      <FieldLabel htmlFor="device-token">Device token</FieldLabel>
      <p className="text-sm font-medium text-destructive">
        Copy this token now. It won&apos;t be shown again. Flash it into the device config, not into git.
      </p>
      <div className="flex gap-2">
        <Input
          id="device-token"
          value={token}
          readOnly
          onFocus={(e) => e.currentTarget.select()}
          className="font-mono"
        />
        <Button variant="outline" onClick={copyToken}>
          {copy === "copied" ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copy === "copied" ? "Copied" : "Copy"}
        </Button>
      </div>
      {copy === "failed" && <FieldError>Copy didn&apos;t work here. Select the token and copy it.</FieldError>}
    </Field>
  );
}
