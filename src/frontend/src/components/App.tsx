import React, { useEffect, useState } from "react";
import { AgentPreview } from "./agents/AgentPreview";
import { ThemeProvider } from "./core/theme/ThemeProvider";

// Simple password for demo access - change this to your desired password
const DEMO_PASSWORD = "Stihl2026";
const AUTH_KEY = "stihl_demo_authenticated";

const App: React.FC = () => {
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem(AUTH_KEY) === "true";
  });
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === DEMO_PASSWORD) {
      localStorage.setItem(AUTH_KEY, "true");
      setIsAuthenticated(true);
      setError("");
    } else {
      setError("Incorrect password");
    }
  };

  // State to store the agent details
  const [agentDetails, setAgentDetails] = useState({
    id: "loading",
    object: "agent",
    created_at: Date.now(),
    name: "Loading...",
    description: "Loading agent details...",
    model: "default",
    metadata: {
      logo: "robot",
    },
    agentPlaygroundUrl: "",
  });

  // Fetch agent details when component mounts
  useEffect(() => {
    const fetchAgentDetails = async () => {
      try {
        const response = await fetch("/agent", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          console.log(
            "Agent details fetched successfully:",
            JSON.stringify(data)
          );
          console.log(
            "Agent details fetched successfully 2:",
            JSON.stringify(response)
          );
          setAgentDetails(data);
        } else {
          console.error("Failed to fetch agent details");
          // Set fallback data if fetch fails
          setAgentDetails({
            id: "fallback",
            object: "agent",
            created_at: Date.now(),
            name: "AI Agent",
            description: "Could not load agent details",
            model: "default",
            metadata: {
              logo: "robot",
            },
            agentPlaygroundUrl: "",
          });
        }
      } catch (error) {
        console.error("Error fetching agent details:", error);
        // Set fallback data if fetch fails
        setAgentDetails({
          id: "error",
          object: "agent",
          created_at: Date.now(),
          name: "AI Agent",
          description: "Error loading agent details",
          model: "default",
          metadata: {
            logo: "robot",
          },
          agentPlaygroundUrl: "",
        });
      }
    };

    fetchAgentDetails();
  }, []);

  // Show login form if not authenticated
  if (!isAuthenticated) {
    return (
      <ThemeProvider>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: "100vh",
            background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
          }}
        >
          <form
            onSubmit={handleLogin}
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              backdropFilter: "blur(10px)",
              padding: "40px",
              borderRadius: "16px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
              minWidth: "320px",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <h1
                style={{
                  color: "#fff",
                  margin: "0 0 8px 0",
                  fontSize: "24px",
                  fontWeight: 600,
                }}
              >
                STIHL Analytics Agent
              </h1>
              <p
                style={{
                  color: "rgba(255, 255, 255, 0.6)",
                  margin: 0,
                  fontSize: "14px",
                }}
              >
                Enter password to access demo
              </p>
            </div>

            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              autoFocus
              style={{
                padding: "14px 16px",
                borderRadius: "8px",
                border: error
                  ? "1px solid #f87171"
                  : "1px solid rgba(255, 255, 255, 0.2)",
                background: "rgba(255, 255, 255, 0.05)",
                color: "#fff",
                fontSize: "16px",
                outline: "none",
              }}
            />

            {error && (
              <p
                style={{
                  color: "#f87171",
                  margin: 0,
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              style={{
                padding: "14px 16px",
                borderRadius: "8px",
                border: "none",
                background: "#F37021",
                color: "#fff",
                fontSize: "16px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Enter Demo
            </button>
          </form>
        </div>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <div className="app-container">
        <AgentPreview
          resourceId="sample-resource-id"
          agentDetails={agentDetails}
        />
      </div>
    </ThemeProvider>
  );
};

export default App;
