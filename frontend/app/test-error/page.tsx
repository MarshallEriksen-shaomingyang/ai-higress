"use client";

export default function TestError() {
  // 这个页面会触发错误边界，用于测试 500 错误页面
  throw new Error("This is a test error to verify the error page works correctly");
}