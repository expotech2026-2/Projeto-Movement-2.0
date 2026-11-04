import { useEffect, useState } from "react";
import { request } from "../services/movementApi";

export function useRoomFeed(roomId, revision) {
  const [feed, setFeed] = useState({
    roomId: null,
    latest: null,
    history: [],
    monthly: [],
    appliances: [],
    devices: [],
    loading: true,
    error: "",
  });
  useEffect(() => {
    if (!roomId) return;
    let active = true;
    let timer;
    const base = `/rooms/${encodeURIComponent(roomId)}`;
    async function load() {
      try {
        const [latest, history, monthly, appliances, devices] =
          await Promise.all([
            request(`${base}/latest`),
            request(`${base}/history?limit=2000`),
            request(`${base}/monthly`),
            request(`${base}/appliances`),
            request(`${base}/devices`),
          ]);
        if (active)
          setFeed({
            roomId,
            latest,
            history,
            monthly,
            appliances,
            devices,
            updatedAt: Date.now(),
            loading: false,
            error: "",
          });
      } catch (error) {
        if (active)
          setFeed((previous) => ({
            ...previous,
            error: error.message,
            loading: false,
          }));
      } finally {
        if (active) timer = window.setTimeout(load, 15000);
      }
    }
    load();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [roomId, revision]);
  return feed.roomId === roomId
    ? feed
    : {
        latest: null,
        history: [],
        monthly: [],
        appliances: [],
        devices: [],
        loading: Boolean(roomId),
        error: feed.error,
      };
}
