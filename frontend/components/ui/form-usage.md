# shadcn/ui Form 组件必填字段使用指南

## 问题说明

shadcn/ui 的 FormField 组件本身没有内置的 `required` 参数，必填标识需要在 FormLabel 组件中手动添加。

## 解决方案

我们已经修改了 `components/ui/form.tsx` 中的 `FormLabel` 组件，添加了 `required` 属性支持。当 `required` 属性为 `true` 时，标签后会自动显示红色星号 (*) 标识。

## 使用方法

### 1. 导入必要的组件

```tsx
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
```

### 2. 在 FormLabel 组件中使用 required 属性

```tsx
<FormField
  control={form.control}
  name="name"
  render={({ field }) => (
    <FormItem>
      <FormLabel required>名称</FormLabel>
      <FormControl>
        <Input placeholder="输入名称" {...field} />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

### 3. 可选字段不使用 required 属性

```tsx
<FormField
  control={form.control}
  name="description"
  render={({ field }) => (
    <FormItem>
      <FormLabel>描述（可选）</FormLabel>
      <FormControl>
        <Textarea placeholder="输入描述" {...field} />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

## 已修改的组件

1. **components/ui/form.tsx** - 修改了 FormLabel 组件，添加了 required 属性支持
2. **components/dashboard/providers/basic-provider-config.tsx** - 为必填字段添加了必填标识
3. **components/dashboard/provider-presets/provider-preset-form.tsx** - 为必填字段添加了必填标识

## 示例表单

查看 `components/examples/demo-form-with-required-fields.tsx` 获取完整的示例代码。

## 必填字段列表

### Provider 表单必填字段

1. **name** - Provider 名称
2. **base_url** - 基础 URL
3. **provider_type** - Provider 类型
4. **transport** - 传输方式
5. **sdk_vendor** - SDK 类型（当传输方式为 SDK 时必填）

### Provider Preset 表单必填字段

1. **preset_id** - 预设 ID
2. **display_name** - 显示名称
3. **base_url** - 基础 URL
4. **provider_type** - Provider 类型
5. **transport** - 传输方式
6. **sdk_vendor** - SDK 类型（当传输方式为 SDK 时必填）