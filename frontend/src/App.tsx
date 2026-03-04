import { SessionProvider } from "./context/SessionContext";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";

function App() {
  return (
    <SessionProvider>
      <div className="h-screen flex flex-col bg-white">
        <Header />
        <main className="flex-1 overflow-hidden">
          <ChatWindow />
        </main>
      </div>
    </SessionProvider>
  );
}

export default App;
