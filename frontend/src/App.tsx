import { SessionProvider } from "./context/SessionContext";

function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen bg-white">TallyPrime AI</div>
    </SessionProvider>
  );
}

export default App;
