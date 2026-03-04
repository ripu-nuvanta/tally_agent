import { SessionProvider } from "./context/SessionContext";
import Header from "./components/Header";

function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen bg-white flex flex-col">
        <Header />
        <main className="flex-1">
          {/* ChatWindow will go here */}
        </main>
      </div>
    </SessionProvider>
  );
}

export default App;
