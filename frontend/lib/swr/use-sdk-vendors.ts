import { SDKVendorsResponse } from "@/http/provider";
import { useApiGet } from "./hooks";

export const useSdkVendors = () => {
  return useApiGet<SDKVendorsResponse>("/providers/sdk-vendors", {
    strategy: "static",
  });
};
