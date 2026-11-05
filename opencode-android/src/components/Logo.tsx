import React from 'react';

export const OpenCodeMark: React.FC<{ size?: number }> = ({ size = 18 }) => (
  <svg
    width={size}
    height={Math.round(size * 1.25)}
    viewBox="0 0 16 20"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={{ flexShrink: 0 }}
  >
    <path d="M12 16H4V8H12V16Z" fill="var(--text-muted)" opacity="0.55" />
    <path d="M12 4H4V16H12V4ZM16 20H0V0H16V20Z" fill="var(--primary)" />
  </svg>
);

export const OpenCodeWordmark: React.FC<{ height?: number }> = ({ height = 22 }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 234 42"
    fill="none"
    style={{ height, width: 'auto', display: 'block' }}
  >
    <g>
      <path d="M18 30H6V18H18V30Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M18 12H6V30H18V12ZM24 36H0V6H24V36Z" fill="var(--text-base)" />
      <path d="M48 30H36V18H48V30Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M36 30H48V12H36V30ZM54 36H36V42H30V6H54V36Z" fill="var(--text-base)" />
      <path d="M84 24V30H66V24H84Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M84 24H66V30H84V36H60V6H84V24ZM66 18H78V12H66V18Z" fill="var(--text-base)" />
      <path d="M108 36H96V18H108V36Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M108 12H96V36H90V6H108V12ZM114 36H108V12H114V36Z" fill="var(--text-base)" />
      <path d="M144 30H126V18H144V30Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M144 12H126V30H144V36H120V6H144V12Z" fill="var(--text-strong)" />
      <path d="M168 30H156V18H168V30Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M168 12H156V30H168V12ZM174 36H150V6H174V36Z" fill="var(--text-strong)" />
      <path d="M198 30H186V18H198V30Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M198 12H186V30H198V12ZM204 36H180V6H198V0H204V36Z" fill="var(--text-strong)" />
      <path d="M234 24V30H216V24H234Z" fill="var(--text-muted)" opacity="0.4" />
      <path d="M216 12V18H228V12H216ZM234 24H216V30H234V36H210V6H234V24Z" fill="var(--text-strong)" />
    </g>
  </svg>
);
