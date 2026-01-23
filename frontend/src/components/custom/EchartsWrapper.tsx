import React from "react";
import ReactECharts from "echarts-for-react";

interface EChartsWrapperProps {
  data: any[];
  columns: string[];
  chartType: string;
  x?: string;
  y?: string;
}
export const EChartsWrapper: React.FC<EChartsWrapperProps> = ({
  data,
  columns,
  chartType,
}) => {
  const getOption = () => {
    const xKey = columns[0];
    const yKeys = columns.slice(1);
    // Mantener datos originales para el tooltip
    const originalData = data;
    const parsedData = data.map((row) => {
      const parsedRow: any = { ...row };
      yKeys.forEach((key) => {
        const value = row[key];
        if (typeof value === "string") {
          parsedRow[key] = parseFloat(value.replace(/[$,]/g, "")) || 0;
        }
        if (isNaN(parsedRow[key])) {
          parsedRow[key] = 0;
        }
      });
      return parsedRow;
    });

    const typeMap: Record<string, string> = {
      BarChart: "bar",
      LineChart: "line",
      Pie: "pie",
      Radar: "radar",
    };

    const echartsType = typeMap[chartType] || chartType.toLowerCase();

    let option: any = {
      tooltip: {
        trigger:
          echartsType === "pie" || echartsType === "radar" ? "item" : "axis",
        formatter: (params: any) => {
          // Manejar array para gráficos de eje (bar, line) o single para pie/radar
          const param = Array.isArray(params) ? params[0] : params;
          const dataIndex = param.dataIndex;
          const dataRow = originalData[dataIndex];

          if (!dataRow) return "";

          // Construir el contenido del tooltip
          let tooltipContent = `<strong>${
            param.name || dataRow[xKey]
          }</strong><br/>`;
          columns.forEach((col) => {
            tooltipContent += `${col}: ${dataRow[col] || "N/A"}<br/>`;
          });

          return tooltipContent;
        },
      },
      legend: { top: "bottom" },
    };

    if (echartsType === "pie") {
      const pieData = parsedData.map((d, index) => ({
        name: d[xKey],
        value: d[yKeys[0]],
        originalIndex: index, // Guardar índice para acceder a datos originales
      }));

      option.series = [
        {
          name: yKeys[0],
          type: "pie",
          radius: "50%",
          data: pieData,
        },
      ];

      option.legend.data = pieData.map((item) => item.name);
    } else if (echartsType === "radar") {
      const indicators = yKeys.map((key) => ({
        name: key,
        max: Math.max(...parsedData.map((d) => d[key])) || 10,
      }));

      option.radar = { indicator: indicators };
      option.series = [
        {
          name: xKey,
          type: "radar",
          data: parsedData.map((d, index) => ({
            value: yKeys.map((key) => d[key]),
            name: d[xKey],
            originalIndex: index, // Guardar índice para acceder a datos originales
          })),
        },
      ];

      option.legend.data = parsedData.map((d) => d[xKey]);
    } else {
      option.grid = {
        bottom: 200, // ← agrega espacio en la parte inferior para evitar superposición
      };
      option.xAxis = {
        type: "category",
        data: parsedData.map((d) => d[xKey]),
        axisLabel: {
          rotate: 90,
          interval: 0,
          fontSize: 11,
          align: "right", // ← Alinea el texto desde el inicio
          verticalAlign: "middle",
        },
      };
      option.yAxis = { type: "value" };
      option.series = yKeys.map((key) => ({
        name: key,
        type: echartsType,
        data: parsedData.map((d) => d[key]),
      }));
      option.legend.data = yKeys;
    }

    return option;
  };

  return (
    <ReactECharts option={getOption()} style={{ height: 400, width: "100%" }} />
  );
};
