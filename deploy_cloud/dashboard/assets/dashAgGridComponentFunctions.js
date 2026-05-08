// Custom AG Grid COMPONENT renderers (React) for dash-ag-grid
var dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// EPC class badge: small colored pill with white letter
dagcomponentfuncs.EpcBadge = function(props) {
    if (!props.value) return null;
    var colors = {
        'A+': '#1B5E20', 'A': '#2E7D32', 'B': '#558B2F', 'C': '#F9A825',
        'D': '#EF6C00', 'E': '#D84315', 'F': '#B71C1C'
    };
    var bg = colors[props.value] || '#999';
    return React.createElement('span', {
        style: {
            backgroundColor: bg,
            color: '#FFF',
            fontWeight: 700,
            padding: '2px 10px',
            borderRadius: '4px',
            display: 'inline-block',
            textAlign: 'center',
            fontSize: '0.85rem',
            minWidth: '24px',
            lineHeight: '1.4'
        }
    }, props.value);
};

// Boolean checkbox renderer (read-only)
dagcomponentfuncs.BoolCheck = function(props) {
    if (props.value == null) return null;
    return React.createElement('span', {
        style: {fontSize: '1rem', textAlign: 'center', display: 'inline-block', width: '100%'}
    }, props.value ? '☑' : '☐');
};
