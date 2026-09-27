//선택한 필지 정보. 지적도(WFS) 응답에서 그대로 뽑아 백엔드로 넘긴다
//  토지특성·개별공시지가 데이터 API 권한이 없어도 면적과 공시지가를 확보할 수 있다
export interface ParcelInfo {
    pnu: string;
    area_m2: number;
    land_price_per_m2: number;   //개별공시지가 (원/㎡)
}

//위도 1도의 거리(m). 경도는 위도에 따라 cos 만큼 짧아진다
const M_PER_DEG = 111_320;

//신발끈 공식으로 링 면적(㎡)을 구한다
//  필지 규모(수십~수백 m)에서는 위도 보정만으로 오차가 0.1% 수준이다
const ringArea = (ring: number[][]): number => {
    if (!ring || ring.length < 3) return 0;

    const latAvg = ring.reduce((sum, [, lat]) => sum + lat, 0) / ring.length;
    const scaleX = M_PER_DEG * Math.cos((latAvg * Math.PI) / 180);

    let sum = 0;
    for (let i = 0; i < ring.length; i += 1) {
        const [lng1, lat1] = ring[i];
        const [lng2, lat2] = ring[(i + 1) % ring.length];
        sum += (lng1 * scaleX) * (lat2 * M_PER_DEG) - (lng2 * scaleX) * (lat1 * M_PER_DEG);
    }
    return Math.abs(sum) / 2;
};

//폴리곤 면적(㎡). 첫 링은 외곽, 나머지는 구멍이라 빼준다
const geometryArea = (geometry: any): number => {
    if (!geometry) return 0;

    const polygons: number[][][][] =
        geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];

    return polygons.reduce((total, polygon) => {
        const outer = ringArea(polygon[0]);
        const holes = polygon.slice(1).reduce((sum, ring) => sum + ringArea(ring), 0);
        return total + outer - holes;
    }, 0);
};

//지적도 feature → 필지 정보
export const parcelFromFeature = (feature: any): ParcelInfo | null => {
    const pnu = feature?.properties?.pnu;
    if (!pnu) return null;

    return {
        pnu,
        area_m2: Math.round(geometryArea(feature.geometry) * 100) / 100,
        land_price_per_m2: Number(feature.properties.jiga ?? 0),
    };
};
