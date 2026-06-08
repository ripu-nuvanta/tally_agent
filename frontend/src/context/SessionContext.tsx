import { createContext, useContext, useState, type ReactNode } from "react";

interface SessionContextValue {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  company: string | null;
  setCompany: (name: string | null) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);

  return (
    <SessionContext.Provider
      value={{ sessionId, setSessionId, company, setCompany }}
    >
      {children}
    </SessionContext.Provider>
  );
}

const _defaultSession: SessionContextValue = {
  sessionId: null,
  setSessionId: () => {},
  company: null,
  setCompany: () => {},
};

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  return ctx ?? _defaultSession;
}
