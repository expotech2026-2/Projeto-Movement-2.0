import { useCallback, useEffect, useState } from "react";
import {
  irTransport,
  roomControl,
  sendIrProtocol,
  setIrTransport,
  setRoomControl,
} from "../services/movementApi";

// Comando do ar-condicionado e temperatura externa (Open-Meteo) da sala.
export function useRoomControl(roomId, refresh) {
  const [state, setState] = useState({
    roomId: null,
    control: null,
    transport: null,
    error: "",
  });

  useEffect(() => {
    if (!roomId) return;
    let active = true;
    Promise.all([roomControl(roomId), irTransport(roomId)])
      .then(([control, transport]) => {
        if (active) setState({ roomId, control, transport, error: "" });
      })
      .catch((error) => {
        if (active) setState({ roomId, control: null, error: error.message });
      });
    return () => {
      active = false;
    };
  }, [roomId, refresh]);

  const send = useCallback(
    async (command) => {
      const control = await setRoomControl(roomId, command);
      setState((previous) => ({ ...previous, roomId, control, error: "" }));
    },
    [roomId],
  );

  const sendProtocol = useCallback(() => sendIrProtocol(roomId), [roomId]);
  const saveTransport = useCallback(
    async (configuration) => {
      const transport = await setIrTransport(roomId, configuration);
      setState((previous) => ({ ...previous, roomId, transport }));
    },
    [roomId],
  );

  return {
    ...state,
    loading: state.roomId !== roomId,
    send,
    sendProtocol,
    saveTransport,
  };
}
