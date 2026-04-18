"use client";

import { useCallback, useReducer } from "react";

type HistoryState = {
  past: string[];
  present: string;
  future: string[];
};

type Action =
  | { type: "SET_PRESENT"; payload: string }
  | { type: "COMMIT"; payload: string }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "RESET"; payload: string };

function reducer(state: HistoryState, action: Action): HistoryState {
  switch (action.type) {
    case "SET_PRESENT":
      return { ...state, present: action.payload };
    case "COMMIT":
      return {
        past: [...state.past, state.present],
        present: action.payload,
        future: [],
      };
    case "UNDO": {
      if (state.past.length === 0) return state;
      const prev = state.past[state.past.length - 1];
      return {
        past: state.past.slice(0, -1),
        present: prev,
        future: [state.present, ...state.future],
      };
    }
    case "REDO": {
      if (state.future.length === 0) return state;
      const [next, ...rest] = state.future;
      return {
        past: [...state.past, state.present],
        present: next,
        future: rest,
      };
    }
    case "RESET":
      return { past: [], present: action.payload, future: [] };
    default:
      return state;
  }
}

export function useBlueprintHistory(initialPresent: string) {
  const [state, dispatch] = useReducer(reducer, {
    past: [],
    present: initialPresent,
    future: [],
  } satisfies HistoryState);

  const setPresent = useCallback((s: string) => {
    dispatch({ type: "SET_PRESENT", payload: s });
  }, []);

  const commit = useCallback((s: string) => {
    dispatch({ type: "COMMIT", payload: s });
  }, []);

  const undo = useCallback(() => {
    dispatch({ type: "UNDO" });
  }, []);

  const redo = useCallback(() => {
    dispatch({ type: "REDO" });
  }, []);

  const reset = useCallback((s: string) => {
    dispatch({ type: "RESET", payload: s });
  }, []);

  return {
    present: state.present,
    setPresent,
    commit,
    undo,
    redo,
    reset,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    /** Для diff: предыдущая зафиксированная версия (если есть) */
    previousCommitted: state.past.length > 0 ? state.past[state.past.length - 1] : null,
  };
}
