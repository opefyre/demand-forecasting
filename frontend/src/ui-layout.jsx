import React,{useRef,useLayoutEffect} from "react";
import { t as uiText,interfaceDirection } from "./localization.mjs";
import { MagnifyingGlass,DotsThree } from "@phosphor-icons/react";
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

// Data collections share the same toolbar, surface, and spacing. Only their
// controls and records vary; a tab cannot supply a competing page layout.
export function Collection({label, controls, actions, children}) {
  return <section className="ui-collection" aria-label={label}>
    <div className="ui-collection-toolbar">
      <div className="ui-collection-controls">{controls}</div>
      <Actions>{actions}</Actions>
    </div>
    <div className="ui-collection-body"><Stack>{children}</Stack></div>
  </section>;
}
export function SearchControl({label, value, onChange}) {
  return <label className="ui-search"><MagnifyingGlass aria-hidden="true"/>
    <input type="search" aria-label={label} placeholder={label} value={value} onChange={e=>onChange(e.target.value)}/>
  </label>;
}
// Connected feeds, historical context and saved observations use one row contract.
export function ConnectionRecord({name,icon:Icon,provider,category,status,tone,meta,actions}) {
  return <tr>
    <td><div className="ui-record-identity"><span className="ui-record-icon" aria-hidden="true"><Icon/></span><strong className="ui-record-heading">{name}</strong></div></td>
    <td>{provider}{category&&<span className="ui-record-meta">{category}</span>}</td>
    <td><span className="ui-record-state" data-tone={tone}>{status}</span>{meta&&<span className="ui-record-meta">{meta}</span>}</td>
    <td><div className="ui-record-actions">{actions}</div></td>
  </tr>;
}

// Shared layout primitives. Pages supply content, never their own appearance.
export function EntrySurface({brand,icon:Icon,children}) {
  return <main className="ui-entry"><section className="ui-panel ui-entry-surface">
    <div className="ui-entry-brand"><Icon aria-hidden="true"/>{brand}</div>
    <Stack>{children}</Stack>
  </section></main>;
}
export function Page({ title, actions, controls, children }) {
  return (
    <section className="ui-page">
      {title && <PageHeader title={title} actions={actions} />}
      {controls && <PageControls>{controls}</PageControls>}
      <div className="ui-page-content">{children}</div>
    </section>
  );
}
export function PageHeader({ title, actions }) {
  return (
    <header className="ui-page-header">
      <h1>{title}</h1>
      {actions && <div className="ui-actions">{actions}</div>}
    </header>
  );
}
export function PageControls({ children }) {
  return <div className="ui-page-controls">{children}</div>;
}
// Open the next surface only after the menu focus scope has closed. Otherwise
// its cleanup can steal focus from the dialog or leave focus on the body.
export function useMenuHandoff(){
  const pending=useRef(null);
  return {
    select:(trigger,action)=>{pending.current={trigger,action};},
    close:event=>{
      if(!pending.current)return;
      event.preventDefault();const {trigger,action}=pending.current;pending.current=null;
      trigger?.focus();queueMicrotask(action);
    },
  };
}
export function ActionMenu({name,items,disabled=false}){
  const trigger=useRef(null),handoff=useMenuHandoff();
  return <DropdownMenu.Root modal={false} dir={interfaceDirection()}>
    <DropdownMenu.Trigger asChild><button ref={trigger} type="button" className="btn secondary" disabled={disabled} aria-label={uiText('Item options for {{name}}',{name})} title={uiText('Item options')}><DotsThree aria-hidden="true"/></button></DropdownMenu.Trigger>
    <DropdownMenu.Portal><DropdownMenu.Content className="ui-menu" align="end" collisionPadding={12} onCloseAutoFocus={handoff.close}>
      {items.map(([label,action])=><DropdownMenu.Item key={label} className="ui-menu-item" onSelect={()=>handoff.select(trigger.current,action)}>{uiText(label)}</DropdownMenu.Item>)}
    </DropdownMenu.Content></DropdownMenu.Portal>
  </DropdownMenu.Root>;
}
export function PageTabs({
  value,
  onChange,
  items,
  label = uiText("View options"),
}) {
  return (
    <nav className="ui-page-nav" aria-label={label}>
      {items.map(([id, title]) => (
        <button
          type="button"
          key={id}
          aria-current={value === id ? "page" : undefined}
          data-selected={value === id}
          onClick={() => onChange(id)}
        >
          {typeof title === "string" ? uiText(title) : title}
        </button>
      ))}
    </nav>
  );
}
export function Panel({ title, description, actions, children }) {
  return (
    <section className="ui-panel">
      <PanelHeader title={title} actions={actions}/>
      <div className="ui-stack">
        {description && <p className="ui-panel-description">{description}</p>}
        {children}
      </div>
    </section>
  );
}
export function PanelHeader({title,actions}) {
  return <header className="ui-panel-header"><div className="ui-panel-heading"><h2 className="ui-panel-title">{title}</h2></div>{actions&&<Actions>{actions}</Actions>}</header>;
}
export function Stack({ as: Tag = "div", children, step, ...props }) {
  const region=useRef(null);
  useLayoutEffect(()=>{if(step!==undefined)region.current?.closest('.ui-dialog-body')?.scrollTo({top:0,behavior:'instant'});},[step]);
  return (
    <Tag {...props} ref={region} className="ui-stack">
      {children}
    </Tag>
  );
}
export function Grid({ columns = 2, actionColumn = false, children }) {
  return (
    <div className={`ui-grid ui-grid-${actionColumn ? "with-action" : columns === 3 ? "three" : "two"}`}>
      {children}
    </div>
  );
}
export function Actions({ children }) {
  return <div className="ui-actions">{children}</div>;
}
export function FieldGroup({ title, children }) {
  return (
    <fieldset className="ui-field-group">
      {title&&<legend>{title}</legend>}
      <Stack>{children}</Stack>
    </fieldset>
  );
}
export function DefinitionList({ rows }) {
  return (
    <dl className="ui-definition-list">
      {rows.map(([label, value], i) => (
        <div key={i}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
export function Disclosure({ title, children }) {
  return (
    <details className="ui-disclosure">
      <summary>{title}</summary>
      <Stack>{children}</Stack>
    </details>
  );
}
