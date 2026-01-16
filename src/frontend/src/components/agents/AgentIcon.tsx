import type { ReactNode } from "react";

import styles from "./AgentIcon.module.css";

export interface IAgentIconProps {
  iconName?: string;
  alt: string;
  iconClassName?: string;
}

export function AgentIcon({
  iconName = "Avatar_Default.svg",
  iconClassName,
  alt = "",
}: IAgentIconProps): ReactNode {
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
