import { useCallback, useEffect, useState } from "react";
import { roomControl, setRoomControl } from "../services/movementApi";

// Comando do ar-condicionado e temperatura externa (Open-Meteo) da sala.
export function useRoomControl(roomId, refresh) {
  const [state, setState] = useState({
    roomId: null,
    control: null,
    error: "",
  });

  useEffect(() => {
    if (!roomId) return;
    let active = true;
    roomControl(roomId)
      .then((control) => {
        if (active) setState({ roomId, control, error: "" });
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
      setState({ roomId, control, error: "" });
    },
    [roomId],
  );

  return { ...state, loading: state.roomId !== roomId, send };
}
