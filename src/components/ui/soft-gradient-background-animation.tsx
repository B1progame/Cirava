import React from 'react';
import { cn } from '@/lib/utils';

interface BgradientAnimProps {
  className?: string;
  animationDuration?: number;
}

const BgradientAnim: React.FC<BgradientAnimProps> = ({ className = '', animationDuration = 5 }) => {
  return <div aria-hidden="true" className={cn('oklch-gradient-bg w-full h-full', className)} style={{ '--gradient-duration': `${animationDuration}s` } as React.CSSProperties} />;
};

export { BgradientAnim };
