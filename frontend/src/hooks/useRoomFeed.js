import { useEffect, useState } from "react";
import { request } from "../services/movementApi";
import {
  HISTORY_LIMIT,
  historySince,
  mergeReadings,
} from "../services/readings";

const POLL_MS = 15000;
// A cada 5 min a sala é recarregada inteira: leituras atrasadas, aparelhos e médias mensais.
const FULL_EVERY = 20;

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
    let running = false;
    let timer;
    let round = 0;
    let current = null;
    const base = `/rooms/${encodeURIComponent(roomId)}`;
    async function load() {
      window.clearTimeout(timer);
      // Com a aba oculta o painel não consulta a API; volta ao ficar visível.
      if (running || document.hidden) return;
      running = true;
      try {
        const full = !current || round % FULL_EVERY === 0;
        const since = full ? null : historySince(current.history);
        const historyPath = `${base}/history?limit=${HISTORY_LIMIT}`;
        const [latest, devices, history, monthly, appliances] =
          await Promise.all([
            request(`${base}/latest`),
            request(`${base}/devices`),
            request(
              since
                ? `${historyPath}&since=${encodeURIComponent(since)}`
                : historyPath,
            ),
            full ? request(`${base}/monthly`) : current.monthly,
            full ? request(`${base}/appliances`) : current.appliances,
          ]);
        round += 1;
        current = {
          latest,
          devices,
          monthly,
          appliances,
          history: since ? mergeReadings(current.history, history) : history,
        };
        if (active)
          setFeed({
            roomId,
            ...current,
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
        running = false;
        if (active) timer = window.setTimeout(load, POLL_MS);
      }
    }
    const wake = () => {
      if (!document.hidden) load();
    };
    document.addEventListener("visibilitychange", wake);
    load();
    return () => {
      active = false;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", wake);
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
