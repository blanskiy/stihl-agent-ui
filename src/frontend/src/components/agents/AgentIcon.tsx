import type { ReactNode } from "react";

import styles from "./AgentIcon.module.css";

export interface IAgentIconProps {
  /**
   * The name of the icon to display
   */
  iconName?: string;
  /**
   * Alt text for the icon
   */
  alt: string;
  /**
   * Optional class name for the icon
   */
  iconClassName?: string;
}

export function AgentIcon({
  iconName = "Avatar_Default.svg",
  iconClassName,
  alt = "",
}: IAgentIconProps): ReactNode {
  // Render orange "S" circle for STIHL branding
  if (iconName === "stihl-logo.png") {
    return (
      <div className={styles.iconContainer}>
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            backgroundColor: "#F37021",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontWeight: "bold",
            fontSize: "16px",
            fontFamily: "Segoe UI, sans-serif",
          }}
        >
          S
        </div>
      </div>
    );
  }

  return (
    <div className={styles.iconContainer}>
      <img
        alt={alt}
        className={iconClassName ?? styles.icon}
        src={`static/assets/template-images/${iconName}`}
      />
    </div>
  );
}


